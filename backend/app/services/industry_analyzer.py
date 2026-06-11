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


class IndustryAnalyzer:
    """行业对标分析"""

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

        # 获取目标股票最新财务数据
        target_financials = DataFetcher.get_financials(db, stock)
        if not target_financials:
            return {
                "error": "目标股票无财务数据",
                "code": code,
                "name": stock.name,
                "industry": stock.industry,
            }

        target_latest = target_financials[-1]

        # 收集同行业所有股票的最新财务数据
        peer_data = []
        for peer in peers:
            try:
                fin_list = DataFetcher.get_financials(db, peer, fetch_if_missing=False)
                if fin_list:
                    latest = fin_list[-1]
                    peer_data.append({
                        "code": peer.code,
                        "name": peer.name,
                        "report_period": latest["report_period"],
                        "revenue": latest.get("revenue"),
                        "net_profit": latest.get("net_profit"),
                        "net_margin": latest.get("net_margin"),
                        "roe": latest.get("roe"),
                        "debt_ratio": latest.get("debt_ratio"),
                        "revenue_growth_yoy": latest.get("revenue_growth_yoy"),
                        "profit_growth_yoy": latest.get("profit_growth_yoy"),
                    })
            except Exception:
                continue

        if len(peer_data) < 2:
            return {
                "code": code,
                "name": stock.name,
                "industry": stock.industry,
                "peer_count": len(peer_data),
                "error": "同行业有效数据不足",
            }

        # 计算行业统计值
        metrics_to_compare = [
            "net_margin", "roe", "debt_ratio", "revenue_growth_yoy", "profit_growth_yoy"
        ]

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

        # 缓存 2 小时
        cache.set(cache_key, result, 7200)
        logger.info(f"行业对标完成: {code} ({stock.industry}), 样本 {len(peer_data)} 家")
        return result

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
                    fin_data = DataFetcher.get_financials(db, stock, fetch_if_missing=False)
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