"""
数据获取服务 — 封装 AkShare 调用

设计要点：
  1. 财务数据使用 ``ak.stock_financial_abstract`` 作为主数据源 —— 单次调用即可
     拿到营收/净利润/净资产/经营现金流/EPS/ROE/资产负债率等完整指标，且数据结构
     稳定（列为报告期，行为指标名）。
  2. 公告使用 ``ak.stock_notice_report`` 的正确签名（symbol=公告类型, date=日期），
     按近期交易日聚合后再按股票代码过滤。
  3. 加入缓存层 + 重试 + 指数退避，避免被限频或偶发连接重置导致整体失败。
  4. 当真实数据源完全不可用时，降级到模拟数据保证可用性。
"""
from __future__ import annotations

import logging
import math
import time
from datetime import date, datetime, timedelta
from typing import Optional

import akshare as ak
from sqlalchemy.orm import Session

from app.cache import cache
from app.config import settings
from app.models.stock import Announcement, Financial, Stock

logger = logging.getLogger(__name__)

# AkShare 调用间隔（避免被限频）
_API_SLEEP = 0.6
# 最大重试次数
_MAX_RETRIES = 3
# 每只股票最多保留的财务报告期数
_MAX_PERIODS = 8
# 公告池回溯的交易日天数
_NOTICE_LOOKBACK_DAYS = 5


def _retry_akshare(func, *args, retries: int = _MAX_RETRIES, **kwargs):
    """带重试 + 指数退避的 AkShare 调用"""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            time.sleep(_API_SLEEP)
            return func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 - akshare 抛出的异常类型不固定
            last_exc = e
            logger.warning(
                "AkShare 调用失败 (attempt %s/%s): %s - %s",
                attempt + 1,
                retries,
                getattr(func, "__name__", str(func)),
                e,
            )
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
    if last_exc is not None:
        raise last_exc
    return None


def _to_float(val) -> Optional[float]:
    """安全地把任意值转成 float，无法解析时返回 None"""
    if val is None:
        return None
    try:
        if isinstance(val, str):
            cleaned = val.strip().replace(",", "")
            if cleaned in ("", "--", "None", "nan", "NaN"):
                return None
            num = float(cleaned)
        else:
            num = float(val)
        if math.isnan(num) or math.isinf(num):
            return None
        return num
    except (ValueError, TypeError):
        return None


def _to_yi(val) -> Optional[float]:
    """元 → 亿元（保留 4 位小数）"""
    num = _to_float(val)
    if num is None:
        return None
    return round(num / 1e8, 4)


def _pinyin_of(name: str) -> tuple[str, str]:
    """把股票名称转成 (全拼, 首字母)，均为小写。用于拼音/首字母搜索。

    例：'平安银行' -> ('pinganyinhang', 'payh')
    pypinyin 不可用时降级为空串，不影响主流程。
    """
    cleaned = (name or "").replace(" ", "")
    if not cleaned:
        return "", ""
    try:
        from pypinyin import Style, lazy_pinyin

        full = "".join(lazy_pinyin(cleaned)).lower()
        initials = "".join(lazy_pinyin(cleaned, style=Style.FIRST_LETTER)).lower()
        return full, initials
    except Exception:  # noqa: BLE001 - pypinyin 缺失/异常时不影响搜索主流程
        return "", ""


class DataFetcher:
    """从 AkShare 拉取 A 股数据并存入数据库"""

    # ========== 股票搜索 ==========

    @staticmethod
    def search_stock(db: Session, keyword: str) -> list[dict]:
        """模糊搜索股票

        性能要点：搜索请求**只查本地数据库**，绝不在请求链路里发起网络同步。
        股票列表由启动时的后台任务预先填充（见 ``ensure_stock_list`` /
        ``background_tasks``）。仅当数据库完全为空（冷启动且后台任务尚未完成）时，
        才退化为一次性同步，避免首个用户面对永久空结果。
        """
        if not keyword or not keyword.strip():
            return []

        keyword = keyword.strip()
        cache_key = f"search:{keyword.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        results = DataFetcher._query_stocks(db, keyword)

        if not results and db.query(Stock.id).first() is None:
            # 数据库尚未填充（冷启动兜底）：同步一次后重查
            logger.info("股票库为空，触发一次性同步")
            DataFetcher._sync_stock_list(db)
            results = DataFetcher._query_stocks(db, keyword)

        if results:
            # 仅缓存非空结果，避免在库填充前把空结果缓存住
            cache.set(cache_key, results, 600)
        return results

    @staticmethod
    def _query_stocks(db: Session, keyword: str) -> list[dict]:
        """纯数据库查询：支持代码、中文名、拼音全拼、拼音首字母。"""
        kw = keyword.strip()
        kw_lower = kw.lower()

        conditions = [Stock.code.contains(kw), Stock.name.contains(kw)]
        # ASCII 关键词（拼音/字母/数字）才匹配拼音列，并用前缀匹配以命中索引
        if kw.isascii():
            conditions.append(Stock.name_pinyin.like(f"{kw_lower}%"))
            conditions.append(Stock.name_initials.like(f"{kw_lower}%"))

        from sqlalchemy import or_

        rows = (
            db.query(Stock)
            .filter(Stock.is_active.is_(True), or_(*conditions))
            .order_by(Stock.code)
            .limit(10)
            .all()
        )
        return [
            {
                "code": s.code,
                "name": s.name,
                "market": s.market,
                "industry": s.industry,
            }
            for s in rows
        ]

    @staticmethod
    def ensure_stock_list(db: Session) -> int:
        """确保股票列表已填充（供启动/后台任务调用）。返回当前库中股票数量。"""
        count = db.query(Stock.id).count()
        if count == 0:
            DataFetcher._sync_stock_list(db)
            count = db.query(Stock.id).count()
        else:
            # 已有数据但可能缺拼音（老库升级），补齐
            DataFetcher._backfill_pinyin(db)
        return count

    @staticmethod
    def _backfill_pinyin(db: Session, batch: int = 2000) -> int:
        """为缺失拼音字段的存量股票补齐拼音（一次性、幂等）。"""
        rows = (
            db.query(Stock)
            .filter(Stock.name_pinyin.is_(None))
            .limit(batch)
            .all()
        )
        if not rows:
            return 0
        for s in rows:
            s.name_pinyin, s.name_initials = _pinyin_of(s.name)
        db.commit()
        logger.info("补齐拼音字段 %s 条", len(rows))
        return len(rows)

    @staticmethod
    def _sync_stock_list(db: Session):
        """同步 A 股股票列表到数据库（带缓存控制，避免短时间重复同步）"""
        if cache.get("stock_list_synced"):
            logger.debug("股票列表近期已同步，跳过")
            return

        try:
            logger.info("开始同步 A 股股票列表...")
            df = _retry_akshare(ak.stock_info_a_code_name)
            if df is None or df.empty:
                logger.warning("获取股票列表为空")
                return

            existing_codes = {c for (c,) in db.query(Stock.code).all()}
            count = 0
            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                name = str(row.get("name", "")).strip().replace(" ", "")
                if not code or not name or len(code) != 6 or not code.isdigit():
                    continue
                if code in existing_codes:
                    continue
                pinyin, initials = _pinyin_of(name)
                db.add(
                    Stock(
                        code=code,
                        name=name,
                        name_pinyin=pinyin,
                        name_initials=initials,
                        market=DataFetcher._guess_market(code),
                    )
                )
                existing_codes.add(code)
                count += 1

            db.commit()
            cache.set("stock_list_synced", True, settings.cache_ttl_stock_list)
            logger.info("股票列表同步完成，新增 %s 只", count)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.error("同步股票列表失败: %s", e)

    @staticmethod
    def _guess_market(code: str) -> str:
        if code.startswith("6"):
            return "SH"
        if code.startswith(("0", "3")):
            return "SZ"
        if code.startswith(("8", "4")):
            return "BJ"
        return "SZ"

    # ========== 行业分类 ==========

    @staticmethod
    def _sync_industries(db: Session, force: bool = False) -> int:
        """同步申万一级行业分类到 Stock.industry

        采用「申万一级行业列表 + 各行业成分股」构建 code→行业 映射后批量写入。
        申万一级共 31 个行业、覆盖全部 A 股，是标准且稳定的分类口径。
        （东方财富个股接口在部分环境会被限流，故不逐只查询。）
        """
        if not force and cache.get("industries_synced"):
            logger.debug("行业分类近期已同步，跳过")
            return 0

        try:
            industry_df = _retry_akshare(ak.sw_index_first_info)
        except Exception as e:  # noqa: BLE001
            logger.error("获取申万一级行业列表失败: %s", e)
            return 0

        if industry_df is None or industry_df.empty:
            logger.warning("申万一级行业列表为空")
            return 0

        # code（去掉 .SI 后缀）→ 行业名称
        code_to_industry: dict[str, str] = {}
        for _, row in industry_df.iterrows():
            sw_code = str(row.get("行业代码", "")).split(".")[0].strip()
            industry_name = str(row.get("行业名称", "")).strip()
            if not sw_code or not industry_name:
                continue
            try:
                cons = _retry_akshare(
                    ak.index_component_sw, symbol=sw_code, retries=2
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("获取行业 %s(%s) 成分股失败: %s", industry_name, sw_code, e)
                continue
            if cons is None or cons.empty or "证券代码" not in cons.columns:
                continue
            for code in cons["证券代码"].astype(str):
                code = code.strip()
                if len(code) == 6 and code.isdigit():
                    code_to_industry[code] = industry_name

        if not code_to_industry:
            logger.warning("未能构建任何行业映射")
            return 0

        # 批量更新数据库
        updated = 0
        try:
            stocks = (
                db.query(Stock)
                .filter(Stock.code.in_(list(code_to_industry.keys())))
                .all()
            )
            for stock in stocks:
                new_industry = code_to_industry.get(stock.code)
                if new_industry and stock.industry != new_industry:
                    stock.industry = new_industry
                    updated += 1
            db.commit()
            cache.set("industries_synced", True, settings.cache_ttl_industry)
            logger.info(
                "行业分类同步完成：映射 %s 只，更新 %s 只",
                len(code_to_industry),
                updated,
            )
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.error("写入行业分类失败: %s", e)
        return updated


    # ========== 股票详情 ==========

    @staticmethod
    def get_stock_detail(db: Session, code: str) -> dict | None:
        """获取股票详情，按需触发数据同步"""
        stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            DataFetcher._sync_stock_list(db)
            stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            return None

        # 按需拉取财务数据（缓存控制）
        cache_key = f"fin_synced:{code}"
        if not stock.financials and not cache.get(cache_key):
            DataFetcher._sync_financials(db, stock)
            cache.set(cache_key, True, settings.cache_ttl_financials)

        # 按需拉取公告
        cache_key_ann = f"ann_synced:{code}"
        if not stock.announcements and not cache.get(cache_key_ann):
            DataFetcher._sync_announcements(db, stock)
            cache.set(cache_key_ann, True, settings.cache_ttl_financials)

        db.refresh(stock)
        return {
            "code": stock.code,
            "name": stock.name,
            "market": stock.market,
            "industry": stock.industry,
            "listing_date": stock.listing_date,
            "is_active": stock.is_active,
        }

    # ========== 财务数据 ==========

    # stock_financial_abstract 指标名 → 解析方式
    # （value 为 None 表示直接取数后转亿元；ratio=True 表示是比率，原样保留）
    _ABSTRACT_METRICS = {
        "revenue": (("营业总收入", "营业收入"), False),
        "net_profit": (("净利润", "归母净利润"), False),
        "total_equity": (("股东权益合计(净资产)", "归属于母公司股东权益合计"), False),
        "operating_cash_flow": (("经营现金流量净额", "经营活动产生的现金流量净额"), False),
        "goodwill": (("商誉",), False),
        "eps": (("基本每股收益",), True),
    }

    @staticmethod
    def _sync_financials(db: Session, stock: Stock):
        """拉取财务数据（主用 stock_financial_abstract，失败则降级模拟数据）"""
        logger.info("开始拉取 %s %s 财务数据...", stock.code, stock.name)

        try:
            df = _retry_akshare(ak.stock_financial_abstract, symbol=stock.code)
        except Exception as e:  # noqa: BLE001
            logger.warning("AkShare 财务接口失败 %s: %s", stock.code, e)
            df = None

        count = 0
        if df is not None and not df.empty:
            try:
                count = DataFetcher._parse_abstract_financials(db, stock, df)
            except Exception as e:  # noqa: BLE001
                db.rollback()
                logger.error("解析财务数据失败 %s: %s", stock.code, e)
                count = 0

        if count > 0:
            logger.info("%s 财务数据同步完成，新增 %s 条", stock.code, count)
            return

        logger.warning("%s 无法获取真实财务数据，使用降级方案", stock.code)
        DataFetcher._use_fallback_financials(db, stock)

    @staticmethod
    def _parse_abstract_financials(db: Session, stock: Stock, df) -> int:
        """解析 stock_financial_abstract 返回的 DataFrame

        结构：列含 8 位日期列（如 '20250331'）+ '选项' + '指标'，行为各项指标。
        """
        if "指标" not in df.columns:
            logger.warning("%s 财务数据缺少 '指标' 列", stock.code)
            return 0

        date_cols = [
            c
            for c in df.columns
            if isinstance(c, str) and c.isdigit() and len(c) == 8
        ]
        if not date_cols:
            logger.warning("%s 财务数据未找到报告期列", stock.code)
            return 0

        # 取最近 N 个报告期
        date_cols = sorted(date_cols, reverse=True)[:_MAX_PERIODS]

        # 构建 指标 → Series 的索引（同名指标取第一次出现）
        metric_index: dict[str, int] = {}
        indicators = df["指标"].tolist()
        for idx, name in enumerate(indicators):
            if isinstance(name, str) and name not in metric_index:
                metric_index[name] = idx

        def get_value(metric_names: tuple[str, ...], col: str):
            for name in metric_names:
                if name in metric_index:
                    return df.iloc[metric_index[name]][col]
            return None

        # 已存在的报告期，避免重复插入
        existing_periods = {
            p
            for (p,) in db.query(Financial.report_period).filter(
                Financial.stock_id == stock.id
            )
        }

        count = 0
        for date_str in date_cols:
            period = DataFetcher._date_to_period(
                f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            )
            if not period or period in existing_periods:
                continue

            revenue = _to_yi(get_value(("营业总收入", "营业收入"), date_str))
            net_profit = _to_yi(get_value(("净利润", "归母净利润"), date_str))
            total_equity = _to_yi(
                get_value(("股东权益合计(净资产)", "归属于母公司股东权益合计"), date_str)
            )
            operating_cash_flow = _to_yi(
                get_value(("经营现金流量净额", "经营活动产生的现金流量净额"), date_str)
            )
            goodwill = _to_yi(get_value(("商誉",), date_str))
            eps = _to_float(get_value(("基本每股收益",), date_str))

            debt_ratio = _to_float(get_value(("资产负债率",), date_str))

            # 由净资产 + 资产负债率推导总资产 / 总负债
            total_assets = None
            total_liability = None
            if total_equity is not None and debt_ratio is not None and 0 <= debt_ratio < 100:
                total_assets = round(total_equity / (1 - debt_ratio / 100), 4)
                total_liability = round(total_assets - total_equity, 4)

            # 全部关键字段都没有 → 跳过该期
            if revenue is None and net_profit is None and total_equity is None:
                continue

            db.add(
                Financial(
                    stock_id=stock.id,
                    report_period=period,
                    report_type="Y" if period.endswith("Q4") else "Q",
                    revenue=revenue,
                    net_profit=net_profit,
                    total_assets=total_assets,
                    total_equity=total_equity,
                    total_liability=total_liability,
                    operating_cash_flow=operating_cash_flow,
                    goodwill=goodwill,
                    eps=eps,
                )
            )
            existing_periods.add(period)
            count += 1

        if count > 0:
            db.commit()
        return count

    @staticmethod
    def _use_fallback_financials(db: Session, stock: Stock):
        """真实数据不可用时，生成并保存模拟财务数据"""
        try:
            from app.services.data_fetcher_fallback import DataFetcherFallback

            mock_financials = DataFetcherFallback.generate_mock_financials(
                db, stock.id, stock.code, stock.name
            )
            saved_count = DataFetcherFallback.save_mock_financials(
                db, stock.id, mock_financials
            )
            if saved_count > 0:
                logger.info("%s 模拟财务数据生成完成，新增 %s 条", stock.code, saved_count)
            else:
                logger.warning("%s 模拟财务数据生成失败或已存在", stock.code)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.error("降级方案失败 %s: %s", stock.code, e)

    @staticmethod
    def _date_to_period(date_str: str) -> Optional[str]:
        """日期字符串转报告期：'2025-03-31' → '2025Q1'"""
        try:
            parts = date_str.split("-")
            year = parts[0]
            month = int(parts[1])
            quarter = (month - 1) // 3 + 1
            return f"{year}Q{quarter}"
        except (IndexError, ValueError):
            return None

    # ========== 财务数据获取（供 API / AI 使用）==========

    @staticmethod
    def get_financials(db: Session, stock: Stock) -> list[dict]:
        """获取股票的财务数据列表（含计算指标）"""
        if not stock.financials:
            DataFetcher._sync_financials(db, stock)
            db.refresh(stock)

        financials_sorted = sorted(
            stock.financials or [],
            key=lambda f: f.report_period,
        )

        results: list[dict] = []
        for fin in financials_sorted:
            item: dict = {
                "report_period": fin.report_period,
                "revenue": fin.revenue,
                "net_profit": fin.net_profit,
                "total_assets": fin.total_assets,
                "total_equity": fin.total_equity,
                "operating_cash_flow": fin.operating_cash_flow,
                "receivables": fin.receivables,
                "inventory": fin.inventory,
                "eps": fin.eps,
                "pe_ratio": fin.pe_ratio,
                "pb_ratio": fin.pb_ratio,
            }

            # 净利率
            if fin.revenue and fin.revenue > 0 and fin.net_profit is not None:
                item["net_margin"] = round(fin.net_profit / fin.revenue * 100, 2)
            else:
                item["net_margin"] = None

            # ROE
            if fin.total_equity and fin.total_equity > 0 and fin.net_profit is not None:
                item["roe"] = round(fin.net_profit / fin.total_equity * 100, 2)
            else:
                item["roe"] = None

            # 资产负债率
            if fin.total_assets and fin.total_assets > 0:
                liability = fin.total_liability or (
                    fin.total_assets - (fin.total_equity or 0)
                )
                item["debt_ratio"] = round(liability / fin.total_assets * 100, 2)
            else:
                item["debt_ratio"] = None

            # 同比增速
            same_q = DataFetcher._find_same_period_last_year(results, fin.report_period)
            if same_q and same_q.get("revenue") and same_q["revenue"] > 0 and fin.revenue:
                item["revenue_growth_yoy"] = round(
                    (fin.revenue - same_q["revenue"]) / abs(same_q["revenue"]) * 100, 2
                )
            else:
                item["revenue_growth_yoy"] = None

            if (
                same_q
                and same_q.get("net_profit")
                and same_q["net_profit"] != 0
                and fin.net_profit is not None
            ):
                item["profit_growth_yoy"] = round(
                    (fin.net_profit - same_q["net_profit"]) / abs(same_q["net_profit"]) * 100,
                    2,
                )
            else:
                item["profit_growth_yoy"] = None

            item["gross_margin"] = None  # 摘要接口未直接提供毛利额，留空

            results.append(item)

        return results

    @staticmethod
    def _find_same_period_last_year(results: list[dict], period: str) -> Optional[dict]:
        """查找去年同期数据"""
        try:
            year = int(period[:4])
            q = period[4:]
            target = f"{year - 1}{q}"
            for r in results:
                if r["report_period"] == target:
                    return r
        except (ValueError, IndexError):
            pass
        return None

    # ========== 公告 ==========

    @staticmethod
    def _fetch_notice_pool(db_today: Optional[date] = None) -> dict[str, list[dict]]:
        """拉取近期公告并按股票代码归集（带缓存，供所有股票复用）

        ``ak.stock_notice_report`` 只能按"日期 + 公告类型"查询全市场公告，
        因此这里回溯最近若干个工作日，聚合后按代码索引。
        """
        cached_pool = cache.get("notice_pool")
        if cached_pool is not None:
            return cached_pool

        pool: dict[str, list[dict]] = {}
        today = db_today or date.today()
        collected_days = 0
        offset = 0
        # 最多向前找 14 个自然日，凑够 _NOTICE_LOOKBACK_DAYS 个有数据的交易日
        while collected_days < _NOTICE_LOOKBACK_DAYS and offset < 14:
            day = today - timedelta(days=offset)
            offset += 1
            if day.weekday() >= 5:  # 跳过周末
                continue
            try:
                df = _retry_akshare(
                    ak.stock_notice_report,
                    symbol="全部",
                    date=day.strftime("%Y%m%d"),
                    retries=1,
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("获取 %s 公告失败: %s", day, e)
                continue
            if df is None or df.empty:
                continue
            collected_days += 1
            for _, row in df.iterrows():
                code = str(row.get("代码", "")).strip()
                if not code:
                    continue
                pool.setdefault(code, []).append(
                    {
                        "title": str(row.get("公告标题", "")).strip(),
                        "date": str(row.get("公告日期", "")).strip(),
                        "url": str(row.get("网址", "")).strip(),
                    }
                )

        cache.set("notice_pool", pool, 3600)
        return pool

    @staticmethod
    def _sync_announcements(db: Session, stock: Stock):
        """拉取近期公告，真实数据缺失时降级到模拟公告"""
        logger.info("开始拉取 %s 公告...", stock.code)
        saved = 0
        try:
            pool = DataFetcher._fetch_notice_pool()
            items = pool.get(stock.code, [])
            saved = DataFetcher._save_announcements(db, stock, items)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.error("同步公告失败 %s: %s", stock.code, e)

        if saved > 0:
            logger.info("%s 公告同步完成，新增 %s 条", stock.code, saved)
            return

        # 没拿到真实公告 → 降级模拟公告
        DataFetcher._use_fallback_announcements(db, stock)

    @staticmethod
    def _save_announcements(db: Session, stock: Stock, items: list[dict]) -> int:
        count = 0
        existing_titles = {
            t
            for (t,) in db.query(Announcement.title).filter(
                Announcement.stock_id == stock.id
            )
        }
        for item in items[:20]:
            title = item.get("title", "").strip()
            if not title or title in existing_titles:
                continue
            pub_date = DataFetcher._parse_date(item.get("date", ""))
            if pub_date is None:
                continue
            db.add(
                Announcement(
                    stock_id=stock.id,
                    title=title,
                    publish_date=pub_date,
                    url=item.get("url", ""),
                )
            )
            existing_titles.add(title)
            count += 1
        if count > 0:
            db.commit()
        return count

    @staticmethod
    def _use_fallback_announcements(db: Session, stock: Stock):
        """生成并保存模拟公告"""
        try:
            from app.services.data_fetcher_fallback import DataFetcherFallback

            mock = DataFetcherFallback.generate_mock_announcements(
                stock.code, stock.name
            )
            count = 0
            existing_titles = {
                t
                for (t,) in db.query(Announcement.title).filter(
                    Announcement.stock_id == stock.id
                )
            }
            for item in mock:
                title = item["title"]
                if title in existing_titles:
                    continue
                db.add(
                    Announcement(
                        stock_id=stock.id,
                        title=title,
                        publish_date=item["publish_date"],
                        url=item.get("url", ""),
                    )
                )
                existing_titles.add(title)
                count += 1
            if count > 0:
                db.commit()
                logger.info("%s 模拟公告生成完成，新增 %s 条", stock.code, count)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.error("生成模拟公告失败 %s: %s", stock.code, e)

    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """解析公告日期，兼容多种格式"""
        if not date_str:
            return None
        text = date_str.strip()[:10]
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None
