"""
数据获取服务 — 封装 AkShare 调用
优化点：
  1. 加入缓存层，避免重复拉取
  2. 统一错误处理和重试逻辑
  3. 日志记录
  4. 更健壮的数据解析
"""
from __future__ import annotations
import logging
import time
from datetime import date, datetime
from typing import Optional

import akshare as ak
from sqlalchemy.orm import Session

from app.models.stock import Stock, Financial, Announcement
from app.cache import cache, cached
from app.config import settings

logger = logging.getLogger(__name__)

# AkShare 调用间隔（避免被限频）
_API_SLEEP = 0.6
# 最大重试次数
_MAX_RETRIES = 3


def _retry_akshare(func, *args, retries: int = _MAX_RETRIES, **kwargs):
    """带重试的 AkShare 调用"""
    for attempt in range(retries):
        try:
            time.sleep(_API_SLEEP)
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"AkShare 调用失败 (attempt {attempt + 1}/{retries}): {func.__name__} - {e}")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)  # 指数退避
    return None


class DataFetcher:
    """从 AkShare 拉取 A 股数据并存入数据库"""

    # ========== 股票搜索 ==========

    @staticmethod
    def search_stock(db: Session, keyword: str) -> list[dict]:
        """模糊搜索股票（优先数据库，缓存加速）"""
        if not keyword or not keyword.strip():
            return []

        keyword = keyword.strip()

        # 先查数据库
        results = (
            db.query(Stock)
            .filter(
                Stock.is_active == True,
                (Stock.code.contains(keyword) | Stock.name.contains(keyword)),
            )
            .limit(10)
            .all()
        )

        if results:
            return [
                {
                    "code": s.code,
                    "name": s.name,
                    "market": s.market,
                    "industry": s.industry,
                }
                for s in results
            ]

        # 数据库没有 → 同步股票列表后重新搜索
        logger.info(f"数据库未命中关键词 '{keyword}'，尝试同步股票列表")
        DataFetcher._sync_stock_list(db)

        results = (
            db.query(Stock)
            .filter(
                Stock.is_active == True,
                (Stock.code.contains(keyword) | Stock.name.contains(keyword)),
            )
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
            for s in results
        ]

    @staticmethod
    def _sync_stock_list(db: Session):
        """同步 A 股股票列表到数据库（带缓存控制）"""
        # 检查缓存标记，避免短时间重复同步
        if cache.get("stock_list_synced"):
            logger.debug("股票列表近期已同步，跳过")
            return

        try:
            logger.info("开始同步 A 股股票列表...")
            df = _retry_akshare(ak.stock_info_a_code_name)
            if df is None or df.empty:
                logger.warning("获取股票列表为空")
                return

            count = 0
            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                name = str(row.get("name", "")).strip()
                if not code or not name or len(code) != 6:
                    continue
                existing = db.query(Stock).filter(Stock.code == code).first()
                if not existing:
                    db.add(Stock(
                        code=code,
                        name=name,
                        market=DataFetcher._guess_market(code),
                    ))
                    count += 1
            db.commit()
            cache.set("stock_list_synced", True, settings.cache_ttl_stock_list)
            logger.info(f"股票列表同步完成，新增 {count} 只")
        except Exception as e:
            db.rollback()
            logger.error(f"同步股票列表失败: {e}")

    @staticmethod
    def _guess_market(code: str) -> str:
        if code.startswith("6"):
            return "SH"
        elif code.startswith(("0", "3")):
            return "SZ"
        elif code.startswith(("8", "4")):
            return "BJ"
        return "SZ"

    # ========== 股票详情 ==========

    @staticmethod
    def get_stock_detail(db: Session, code: str) -> dict | None:
        """获取股票详情，触发数据同步"""
        stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            DataFetcher._sync_stock_list(db)
            stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            return None

        # 检查是否需要拉取财务数据（有缓存控制）
        cache_key = f"fin_synced:{code}"
        if not stock.financials and not cache.get(cache_key):
            DataFetcher._sync_financials(db, stock)
            cache.set(cache_key, True, settings.cache_ttl_financials)

        # 检查是否需要拉取公告
        cache_key_ann = f"ann_synced:{code}"
        if not stock.announcements and not cache.get(cache_key_ann):
            DataFetcher._sync_announcements(db, stock)
            cache.set(cache_key_ann, True, settings.cache_ttl_financials)

        return {
            "code": stock.code,
            "name": stock.name,
            "market": stock.market,
            "industry": stock.industry,
            "listing_date": stock.listing_date,
            "is_active": stock.is_active,
        }

    # ========== 财务数据 ==========

    @staticmethod
    def _sync_financials(db: Session, stock: Stock):
        """拉取财务数据（三大报表核心字段）"""
        logger.info(f"开始拉取 {stock.code} {stock.name} 财务数据...")
        
        # 先尝试 AkShare 接口
        ak_attempt_success = False
        
        try:
            # 尝试使用 stock_financial_report_sina 接口（测试中这个接口可用）
            df = _retry_akshare(
                ak.stock_financial_report_sina,
                stock=stock.code,
                symbol="利润表",
            )

            if df is not None and not df.empty:
                logger.info(f"AkShare 接口成功获取数据，形状: {df.shape}")
                
                # 解析新浪财务数据
                count = DataFetcher._parse_sina_financials(db, stock, df)
                if count > 0:
                    ak_attempt_success = True
                    logger.info(f"{stock.code} AkShare 财务数据同步完成，新增 {count} 条")
                else:
                    logger.warning(f"{stock.code} AkShare 数据解析失败或数据为空")
            else:
                logger.warning(f"{stock.code} AkShare 返回空数据")
                
        except Exception as e:
            logger.warning(f"AkShare 接口失败 {stock.code}: {e}")
        
        # 如果 AkShare 失败，使用降级方案
        if not ak_attempt_success:
            logger.info(f"{stock.code} 使用降级方案生成模拟数据")
            DataFetcher._use_fallback_financials(db, stock)
    
    @staticmethod
    def _parse_sina_financials(db: Session, stock: Stock, df) -> int:
        """解析新浪财务数据"""
        count = 0
        
        # 新浪报表的列通常是日期格式如 "20250331"
        date_columns = []
        for col in df.columns:
            if isinstance(col, str) and col.isdigit() and len(col) == 8:
                date_columns.append(col)
        
        if not date_columns:
            logger.warning(f"{stock.code} 未找到日期列")
            return 0
        
        # 按日期排序，取最近4个报告期
        date_columns_sorted = sorted(date_columns, reverse=True)[:4]
        
        for date_str in date_columns_sorted:
            # 转换日期格式 "20250331" → "2025Q1"
            period = DataFetcher._date_to_period(
                f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            )
            if not period:
                continue
            
            # 检查是否已存在
            if db.query(Financial).filter(
                Financial.stock_id == stock.id,
                Financial.report_period == period,
            ).first():
                continue
            
            # 从 DataFrame 中提取数据
            revenue = DataFetcher._get_sina_value(df, date_str, "营业收入")
            net_profit = DataFetcher._get_sina_value(df, date_str, "净利润")
            
            if revenue is None and net_profit is None:
                continue
            
            fin = Financial(
                stock_id=stock.id,
                report_period=period,
                report_type="Y" if period.endswith("Q4") else "Q",
                revenue=revenue,
                net_profit=net_profit,
                total_assets=None,  # 新浪接口可能没有这些字段
                total_equity=None,
                operating_cash_flow=None,
            )
            db.add(fin)
            count += 1
        
        if count > 0:
            db.commit()
        
        return count

    @staticmethod
    def _sync_financials_fallback(db: Session, stock: Stock):
        """备选财务数据拉取方案"""
        try:
            logger.info(f"尝试备选方案拉取 {stock.code} 财务数据...")
            # 使用利润表接口
            df = _retry_akshare(
                ak.stock_financial_report_sina,
                stock=stock.code,
                symbol="利润表",
            )
            if df is None or df.empty:
                return

            # 尝试解析新浪财务数据
            for col in list(df.columns)[1:9]:  # 最近8个报告期
                if not isinstance(col, str) or not col.isdigit():
                    continue

                period = DataFetcher._date_to_period(
                    f"{col[:4]}-{col[4:6]}-{col[6:8]}"
                )
                if not period:
                    continue

                if db.query(Financial).filter(
                    Financial.stock_id == stock.id,
                    Financial.report_period == period,
                ).first():
                    continue

                revenue = DataFetcher._get_sina_value(df, col, "营业收入")
                net_profit = DataFetcher._get_sina_value(df, col, "净利润")

                if revenue is None and net_profit is None:
                    continue

                fin = Financial(
                    stock_id=stock.id,
                    report_period=period,
                    report_type="Y" if period.endswith("Q4") else "Q",
                    revenue=revenue,
                    net_profit=net_profit,
                )
                db.add(fin)

            db.commit()
            logger.info(f"{stock.code} 备选方案同步完成")
        except Exception as e:
            db.rollback()
            logger.error(f"备选方案也失败 {stock.code}: {e}")

    @staticmethod
    def _get_sina_value(df, col: str, field: str) -> Optional[float]:
        """从新浪报表 DataFrame 获取某字段值"""
        try:
            if field not in df.iloc[:, 0].values:
                return None
            row = df[df.iloc[:, 0] == field]
            if row.empty or col not in row.columns:
                return None
            val = row.iloc[0][col]
            if val is None or str(val).strip() in ("", "None", "nan"):
                return None
            return round(float(val) / 1e8, 4)  # 元 → 亿元
        except (ValueError, TypeError, IndexError):
            return None

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

    @staticmethod
    def _parse_float(row, field: str) -> Optional[float]:
        """安全解析浮点数"""
        try:
            val = row.get(field)
            if val is None or str(val).strip() in ("", "None", "nan", "--"):
                return None
            result = float(val)
            # 如果数值很大，可能是元单位，转亿
            if abs(result) > 1e9:
                return round(result / 1e8, 4)
            return round(result, 4)
        except (ValueError, TypeError):
            return None

    # ========== 财务数据获取（供 AI 使用）==========

    @staticmethod
    def get_financials(db: Session, stock: Stock) -> list[dict]:
        """获取股票的财务数据列表（含计算指标）"""
        if not stock.financials:
            DataFetcher._sync_financials(db, stock)

        # 按报告期排序
        financials_sorted = sorted(
            stock.financials or [],
            key=lambda f: f.report_period,
        )

        results = []
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

            # 计算净利率
            if fin.revenue and fin.revenue > 0 and fin.net_profit is not None:
                item["net_margin"] = round(fin.net_profit / fin.revenue * 100, 2)
            else:
                item["net_margin"] = None

            # 计算 ROE
            if fin.total_equity and fin.total_equity > 0 and fin.net_profit is not None:
                item["roe"] = round(fin.net_profit / fin.total_equity * 100, 2)
            else:
                item["roe"] = None

            # 计算资产负债率
            if fin.total_assets and fin.total_assets > 0:
                liability = fin.total_liability or (
                    fin.total_assets - (fin.total_equity or 0)
                )
                item["debt_ratio"] = round(liability / fin.total_assets * 100, 2)
            else:
                item["debt_ratio"] = None

            # 同比增速：找去年同期
            same_q = DataFetcher._find_same_period_last_year(results, fin.report_period)
            if same_q:
                if same_q.get("revenue") and same_q["revenue"] > 0 and fin.revenue:
                    item["revenue_growth_yoy"] = round(
                        (fin.revenue - same_q["revenue"]) / abs(same_q["revenue"]) * 100, 2
                    )
                else:
                    item["revenue_growth_yoy"] = None

                if same_q.get("net_profit") and same_q["net_profit"] != 0 and fin.net_profit:
                    item["profit_growth_yoy"] = round(
                        (fin.net_profit - same_q["net_profit"]) / abs(same_q["net_profit"]) * 100, 2
                    )
                else:
                    item["profit_growth_yoy"] = None
            else:
                item["revenue_growth_yoy"] = None
                item["profit_growth_yoy"] = None

            # 毛利率（暂缺毛利数据，留空）
            item["gross_margin"] = None

            results.append(item)

        return results

    @staticmethod
    def _find_same_period_last_year(results: list[dict], period: str) -> Optional[dict]:
        """查找去年同期数据"""
        try:
            year = int(period[:4])
            q = period[4:]  # 如 "Q1"
            target = f"{year - 1}{q}"
            for r in results:
                if r["report_period"] == target:
                    return r
        except (ValueError, IndexError):
            pass
        return None

    # ========== 公告 ==========

    @staticmethod
    def _sync_announcements(db: Session, stock: Stock):
        """拉取近期公告"""
        logger.info(f"开始拉取 {stock.code} 公告...")
        try:
            df = _retry_akshare(ak.stock_notice_report, symbol=stock.code)
            if df is None or df.empty:
                # 尝试全量公告按名称过滤
                df = _retry_akshare(ak.stock_notice_report, symbol="all")
                if df is None or df.empty:
                    logger.warning(f"{stock.code} 无公告数据")
                    return
                # 按股票名称过滤
                df = df[df["name"].str.contains(stock.name, na=False)]

            df = df.sort_values("notice_date", ascending=False).head(20)

            count = 0
            for _, row in df.iterrows():
                title = str(row.get("title", "")).strip()
                if not title:
                    continue

                pub_date_str = str(row.get("notice_date", ""))
                try:
                    pub_date = datetime.strptime(pub_date_str[:10], "%Y-%m-%d").date()
                except (ValueError, IndexError):
                    continue

                url = str(row.get("pdf_link", "")) if "pdf_link" in row.index else ""

                # 避免重复
                if db.query(Announcement).filter(
                    Announcement.stock_id == stock.id,
                    Announcement.title == title,
                ).first():
                    continue

                db.add(Announcement(
                    stock_id=stock.id,
                    title=title,
                    publish_date=pub_date,
                    url=url,
                ))
                count += 1

            db.commit()
            logger.info(f"{stock.code} 公告同步完成，新增 {count} 条")
        except Exception as e:
            db.rollback()
            logger.error(f"同步公告失败 {stock.code}: {e}")

    @staticmethod
    def _use_fallback_financials(db: Session, stock: Stock):
        """使用降级方案生成财务数据"""
        try:
            # 导入降级模块
            from app.services.data_fetcher_fallback import DataFetcherFallback
            
            # 生成模拟数据
            mock_financials = DataFetcherFallback.generate_mock_financials(
                db, stock.id, stock.code, stock.name
            )
            
            # 保存到数据库
            saved_count = DataFetcherFallback.save_mock_financials(db, stock.id, mock_financials)
            
            if saved_count > 0:
                logger.info(f"{stock.code} 模拟财务数据生成完成，新增 {saved_count} 条")
            else:
                logger.warning(f"{stock.code} 模拟财务数据生成失败或已存在")
                
        except Exception as e:
            logger.error(f"降级方案失败 {stock.code}: {e}")
            db.rollback()
    
    @staticmethod
    def _sync_financials_fallback(db: Session, stock: Stock):
        """备选财务数据拉取方案（旧版本，保持兼容）"""
        try:
            logger.info(f"尝试备选方案拉取 {stock.code} 财务数据...")
            # 使用利润表接口
            df = _retry_akshare(
                ak.stock_financial_report_sina,
                stock=stock.code,
                symbol="利润表",
            )
            if df is None or df.empty:
                return

            count = 0
            for col in list(df.columns)[1:9]:  # 最近8个报告期
                if not isinstance(col, str) or not col.isdigit():
                    continue

                period = DataFetcher._date_to_period(
                    f"{col[:4]}-{col[4:6]}-{col[6:8]}"
                )
                if not period:
                    continue

                if db.query(Financial).filter(
                    Financial.stock_id == stock.id,
                    Financial.report_period == period,
                ).first():
                    continue

                revenue = DataFetcher._get_sina_value(df, col, "营业收入")
                net_profit = DataFetcher._get_sina_value(df, col, "净利润")

                if revenue is None and net_profit is None:
                    continue

                fin = Financial(
                    stock_id=stock.id,
                    report_period=period,
                    report_type="Y" if period.endswith("Q4") else "Q",
                    revenue=revenue,
                    net_profit=net_profit,
                )
                db.add(fin)
                count += 1

            db.commit()
            logger.info(f"{stock.code} 备选方案同步完成")
        except Exception as e:
            db.rollback()
            logger.error(f"备选方案也失败 {stock.code}: {e}")