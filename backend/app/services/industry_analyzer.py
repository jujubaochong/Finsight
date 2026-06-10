"""
行业对标分析服务 — 计算同行业公司的财务指标对比
"""
from __future__ import annotations
import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func

from app.models.stock import Stock, Financial, IndustryBenchmark
from app.services.data_fetcher import DataFetcher
from app.cache import cache

logger = logging.getLogger(__name__)

# 行业财务数据后台补拉线程池（限并发，避免给数据源过大压力）
from concurrent.futures import ThreadPoolExecutor

_backfill_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="industry_backfill")
_backfill_inflight: set[str] = set()


class IndustryAnalyzer:
    """行业对标分析"""

    @staticmethod
    def _trigger_backfill(industry: str):
        """异步触发某行业的财务数据补拉（去重，避免重复任务）。"""
        if not industry or industry in _backfill_inflight:
            return
        _backfill_inflight.add(industry)

        def _job():
            from app.database import SessionLocal

            db = SessionLocal()
            try:
                IndustryAnalyzer.backfill_industry_financials(db, industry)
                # 补拉完成后，对标结果会在短 TTL 缓存过期后自动重算
            except Exception as e:  # noqa: BLE001
                logger.debug("行业 %s 后台补拉失败: %s", industry, e)
            finally:
                db.close()
                _backfill_inflight.discard(industry)

        try:
            _backfill_executor.submit(_job)
        except Exception:  # noqa: BLE001
            _backfill_inflight.discard(industry)

    @staticmethod
    def get_industry_comparison(db: Session, code: str) -> dict:
        """
        获取目标股票的行业对标数据
        返回：目标股票指标 + 行业均值/中位数 + 行业排名 + 同行列表
        """
        stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            return {"error": "股票不存在"}

        if not stock.industry:
            return {"error": "该股票缺少行业分类信息", "code": code, "name": stock.name}

        # 检查缓存
        cache_key = f"industry_comp:{code}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # 获取同行业股票
        peers = (
            db.query(Stock)
            .filter(
                Stock.industry == stock.industry,
                Stock.is_active == True,
            )
            .all()
        )

        if len(peers) < 2:
            return {
                "error": "同行业股票数量不足，无法对标",
                "code": code,
                "name": stock.name,
                "industry": stock.industry,
            }

        # 获取目标股票最新财务数据（目标股票一定会拉，因为用户正在看它）
        target_financials = DataFetcher.get_financials(db, stock)
        if not target_financials:
            return {
                "error": "目标股票无财务数据",
                "code": code,
                "name": stock.name,
                "industry": stock.industry,
            }

        target_latest = target_financials[-1]

        # 收集同行业股票的最新财务数据
        # 性能关键：只读取数据库中【已有】财务数据的同行，绝不在请求链路里
        # 对每个同行逐个联网拉取（否则上百家同行会导致请求超时）。
        # 缺失的同行财务数据由后台任务异步补齐，下次访问即可纳入对标。
        peer_data = IndustryAnalyzer._collect_peer_data_from_db(db, peers, code)

        # 确保目标股票自身在对标列表中（即使刚拉到、其它同行还没补齐）
        if not any(p["code"] == code for p in peer_data):
            peer_data.append(IndustryAnalyzer._latest_to_peer_row(stock, target_latest))

        if len(peer_data) < 2:
            # 同行数据太少 → 触发后台补拉，本次先返回 pending
            IndustryAnalyzer._trigger_backfill(stock.industry)
            return {
                "code": code,
                "name": stock.name,
                "industry": stock.industry,
                "peer_count": len(peer_data),
                "target_metrics": {
                    "report_period": target_latest["report_period"],
                    "revenue": target_latest.get("revenue"),
                    "net_profit": target_latest.get("net_profit"),
                    "net_margin": target_latest.get("net_margin"),
                    "roe": target_latest.get("roe"),
                    "debt_ratio": target_latest.get("debt_ratio"),
                    "revenue_growth_yoy": target_latest.get("revenue_growth_yoy"),
                    "profit_growth_yoy": target_latest.get("profit_growth_yoy"),
                },
                "industry_stats": {},
                "rankings": {},
                "top_peers": peer_data,
                "pending": True,
                "message": "同行业财务数据正在后台补充，稍后刷新可看到完整对标。",
            }

        # 计算行业统计值
        metrics_to_compare = [
            "net_margin", "roe", "debt_ratio", "revenue_growth_yoy", "profit_growth_yoy"
        ]

        # 若仍有较多同行缺财务数据，后台继续补齐（不阻塞本次返回）
        if len(peer_data) < len(peers) * 0.6:
            IndustryAnalyzer._trigger_backfill(stock.industry)

        industry_stats = {}
        rankings = {}

        for metric in metrics_to_compare:
            values = [p[metric] for p in peer_data if p.get(metric) is not None]
            if not values:
                continue

            values_sorted = sorted(values)
            n = len(values_sorted)

            industry_stats[metric] = {
                "avg": round(sum(values) / n, 2),
                "median": round(values_sorted[n // 2], 2),
                "max": round(max(values), 2),
                "min": round(min(values), 2),
                "count": n,
            }

            # 计算目标股票的排名
            target_val = target_latest.get(metric)
            if target_val is not None:
                # 对于 debt_ratio，越低越好；其他越高越好
                if metric == "debt_ratio":
                    rank = sum(1 for v in values if v < target_val) + 1
                else:
                    rank = sum(1 for v in values if v > target_val) + 1
                rankings[metric] = {
                    "rank": rank,
                    "total": n,
                    "percentile": round((1 - rank / n) * 100, 1),
                }

        # 获取 top 同行（按营收排序）
        peer_data_sorted = sorted(
            peer_data,
            key=lambda x: x.get("revenue") or 0,
            reverse=True,
        )
        top_peers = peer_data_sorted[:10]  # 取前10大

        result = {
            "code": code,
            "name": stock.name,
            "industry": stock.industry,
            "target_metrics": {
                "report_period": target_latest["report_period"],
                "revenue": target_latest.get("revenue"),
                "net_profit": target_latest.get("net_profit"),
                "net_margin": target_latest.get("net_margin"),
                "roe": target_latest.get("roe"),
                "debt_ratio": target_latest.get("debt_ratio"),
                "revenue_growth_yoy": target_latest.get("revenue_growth_yoy"),
                "profit_growth_yoy": target_latest.get("profit_growth_yoy"),
            },
            "industry_stats": industry_stats,
            "rankings": rankings,
            "peer_count": len(peer_data),
            "top_peers": top_peers,
        }

        # 缓存：数据较完整时缓存 2 小时；仍在补齐时只缓存 3 分钟，
        # 以便后台补全后较快反映到对标结果中。
        ttl = 7200 if len(peer_data) >= len(peers) * 0.6 else 180
        cache.set(cache_key, result, ttl)
        logger.info(f"行业对标完成: {code} ({stock.industry}), 样本 {len(peer_data)} 家")
        return result

    @staticmethod
    def _latest_to_peer_row(stock: Stock, latest: dict) -> dict:
        """把一条财务记录整理成对标行"""
        return {
            "code": stock.code,
            "name": stock.name,
            "report_period": latest.get("report_period"),
            "revenue": latest.get("revenue"),
            "net_profit": latest.get("net_profit"),
            "net_margin": latest.get("net_margin"),
            "roe": latest.get("roe"),
            "debt_ratio": latest.get("debt_ratio"),
            "revenue_growth_yoy": latest.get("revenue_growth_yoy"),
            "profit_growth_yoy": latest.get("profit_growth_yoy"),
        }

    @staticmethod
    def _collect_peer_data_from_db(db: Session, peers: list[Stock], code: str) -> list[dict]:
        """仅从数据库已有数据计算同行最新财务指标（不触发任何网络请求）。

        通过 stock.financials 关系直接读取（SQLAlchemy 已加载），对每个有财务
        数据的同行取最新报告期并计算指标。无数据的同行直接跳过，由后台补齐。
        """
        peer_data: list[dict] = []
        for peer in peers:
            fins = peer.financials
            if not fins:
                continue
            # 取最新报告期那条
            latest_fin = max(fins, key=lambda f: f.report_period or "")
            metrics = IndustryAnalyzer._compute_metrics(peer, latest_fin)
            peer_data.append(metrics)
        return peer_data

    @staticmethod
    def _compute_metrics(stock: Stock, fin) -> dict:
        """由单条 Financial 计算对标所需指标（与 DataFetcher.get_financials 口径一致）。"""
        net_margin = None
        if fin.revenue and fin.revenue > 0 and fin.net_profit is not None:
            net_margin = round(fin.net_profit / fin.revenue * 100, 2)
        roe = None
        if fin.total_equity and fin.total_equity > 0 and fin.net_profit is not None:
            roe = round(fin.net_profit / fin.total_equity * 100, 2)
        debt_ratio = None
        if fin.total_assets and fin.total_assets > 0:
            liability = fin.total_liability or (fin.total_assets - (fin.total_equity or 0))
            debt_ratio = round(liability / fin.total_assets * 100, 2)
        return {
            "code": stock.code,
            "name": stock.name,
            "report_period": fin.report_period,
            "revenue": fin.revenue,
            "net_profit": fin.net_profit,
            "net_margin": net_margin,
            "roe": roe,
            "debt_ratio": debt_ratio,
            "revenue_growth_yoy": None,  # 同比需历史期，对标用最新值即可
            "profit_growth_yoy": None,
        }

    @staticmethod
    def backfill_industry_financials(db: Session, industry: str, max_stocks: int = 30) -> int:
        """后台任务：为某行业中缺少财务数据的股票补拉（限量，避免一次拉太多）。"""
        peers = (
            db.query(Stock)
            .filter(Stock.industry == industry, Stock.is_active == True)
            .all()
        )
        filled = 0
        for peer in peers:
            if filled >= max_stocks:
                break
            if not peer.financials:
                try:
                    DataFetcher._sync_financials(db, peer)
                    filled += 1
                except Exception as e:  # noqa: BLE001
                    logger.debug("补拉 %s 财务失败: %s", peer.code, e)
        if filled:
            logger.info("行业 %s 补拉了 %s 只股票的财务数据", industry, filled)
        return filled

    @staticmethod
    def get_industry_list(db: Session) -> list[dict]:
        """获取所有行业列表及其股票数"""
        results = (
            db.query(
                Stock.industry,
                sql_func.count(Stock.id).label("count"),
            )
            .filter(Stock.industry != None, Stock.is_active == True)
            .group_by(Stock.industry)
            .order_by(sql_func.count(Stock.id).desc())
            .all()
        )
        return [
            {"industry": r[0], "stock_count": r[1]}
            for r in results
            if r[0]
        ]

    @staticmethod
    def get_industry_peers(db: Session, code: str, limit: int = 20) -> list[dict]:
        """获取同行业股票列表"""
        stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock or not stock.industry:
            return []

        peers = (
            db.query(Stock)
            .filter(
                Stock.industry == stock.industry,
                Stock.is_active == True,
                Stock.code != code,
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "code": p.code,
                "name": p.name,
                "market": p.market,
                "industry": p.industry,
            }
            for p in peers
        ]

    @staticmethod
    def update_all_industry_benchmarks(db: Session) -> dict:
        """更新所有行业的基准数据（用于后台定时任务）"""
        from app.models.stock import IndustryBenchmark
        
        # 获取所有行业
        industries = IndustryAnalyzer.get_industry_list(db)
        logger.info(f"开始更新 {len(industries)} 个行业的基准数据")
        
        updated_count = 0
        error_count = 0
        
        for industry_info in industries:
            industry = industry_info["industry"]
            try:
                # 获取该行业所有股票的最新财务数据
                peers = (
                    db.query(Stock)
                    .filter(Stock.industry == industry, Stock.is_active == True)
                    .all()
                )
                
                if len(peers) < 3:
                    logger.debug(f"行业 {industry} 样本不足，跳过")
                    continue
                
                # 收集所有财务指标
                all_financials = []
                for stock in peers:
                    fin_data = DataFetcher.get_financials(db, stock)
                    if fin_data and len(fin_data) > 0:
                        all_financials.extend(fin_data)
                
                if not all_financials:
                    logger.debug(f"行业 {industry} 无财务数据，跳过")
                    continue
                
                # 按报告期分组
                periods = {}
                for fin in all_financials:
                    period = fin.get("report_period")
                    if not period:
                        continue
                    if period not in periods:
                        periods[period] = []
                    periods[period].append(fin)
                
                # 只处理最新的报告期
                if not periods:
                    continue
                    
                latest_period = max(periods.keys())
                latest_fins = periods[latest_period]
                
                # 计算各指标的统计值
                metrics = ["net_margin", "roe", "debt_ratio", "revenue", "net_profit"]
                
                for metric in metrics:
                    values = [f.get(metric) for f in latest_fins if f.get(metric) is not None]
                    if not values:
                        continue
                    
                    # 计算统计值
                    values_sorted = sorted(values)
                    n = len(values_sorted)
                    
                    # 检查是否已存在
                    existing = db.query(IndustryBenchmark).filter(
                        IndustryBenchmark.industry == industry,
                        IndustryBenchmark.report_period == latest_period,
                        IndustryBenchmark.metric_name == metric,
                    ).first()
                    
                    if existing:
                        existing.avg_value = round(sum(values) / n, 4)
                        existing.median_value = round(values_sorted[n // 2], 4)
                        existing.max_value = round(max(values), 4)
                        existing.min_value = round(min(values), 4)
                        existing.sample_count = n
                    else:
                        benchmark = IndustryBenchmark(
                            industry=industry,
                            report_period=latest_period,
                            metric_name=metric,
                            avg_value=round(sum(values) / n, 4),
                            median_value=round(values_sorted[n // 2], 4),
                            max_value=round(max(values), 4),
                            min_value=round(min(values), 4),
                            sample_count=n,
                        )
                        db.add(benchmark)
                    
                    updated_count += 1
                
                db.commit()
                logger.debug(f"行业 {industry} 基准数据更新完成，报告期 {latest_period}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"更新行业 {industry} 基准数据失败: {e}")
                db.rollback()
        
        result = {
            "total_industries": len(industries),
            "updated_metrics": updated_count,
            "errors": error_count,
        }
        
        logger.info(f"行业基准数据更新完成: {result}")
        return result