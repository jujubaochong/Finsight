"""
后台任务调度
"""
import asyncio
import logging
from datetime import datetime
from contextlib import contextmanager

from app.database import SessionLocal
from app.services.alert_monitor import AlertMonitor
from app.services.industry_analyzer import IndustryAnalyzer
from app.services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)


@contextmanager
def get_db_session():
    """获取数据库会话上下文管理器"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def run_anomaly_scan_task():
    """定时运行异常扫描任务"""
    while True:
        try:
            logger.info("开始定时异常扫描...")
            with get_db_session() as db:
                alerts = AlertMonitor.scan_watchlist_alerts(db)
                logger.info(f"定时异常扫描完成，发现 {len(alerts)} 个异常")
        except Exception as e:
            logger.error(f"异常扫描任务失败: {e}")
        
        # 每小时运行一次
        await asyncio.sleep(3600)


async def update_industry_benchmarks_task():
    """定时更新行业基准数据"""
    while True:
        try:
            logger.info("开始更新行业基准数据...")
            with get_db_session() as db:
                IndustryAnalyzer.update_all_industry_benchmarks(db)
                logger.info("行业基准数据更新完成")
        except Exception as e:
            logger.error(f"行业基准更新任务失败: {e}")
        
        # 每天凌晨2点运行一次
        await asyncio.sleep(24 * 3600)


async def cleanup_old_alerts_task():
    """清理过期异常记录"""
    while True:
        try:
            logger.info("开始清理过期异常记录...")
            with get_db_session() as db:
                deleted = AlertMonitor.cleanup_old_alerts(db, days_to_keep=30)
                logger.info(f"清理完成，删除 {deleted} 条过期记录")
        except Exception as e:
            logger.error(f"清理任务失败: {e}")
        
        # 每天运行一次
        await asyncio.sleep(24 * 3600)


async def seed_stock_list_task():
    """启动后立即填充股票列表，保证搜索一开始就走纯数据库的快路径。"""
    await asyncio.sleep(2)
    try:
        logger.info("预填充股票列表...")
        with get_db_session() as db:
            count = DataFetcher.ensure_stock_list(db)
            logger.info("股票列表就绪，共 %s 只", count)
    except Exception as e:
        logger.error(f"预填充股票列表失败: {e}")


async def sync_industries_task():
    """定时同步股票列表与行业分类（启动后稍作延迟，避免与启动初始化抢占）"""
    # 启动后延迟，确保应用就绪
    await asyncio.sleep(15)
    while True:
        try:
            logger.info("开始同步股票列表与行业分类...")
            with get_db_session() as db:
                # 行业映射依赖股票列表，先确保列表存在
                DataFetcher.ensure_stock_list(db)
                updated = DataFetcher._sync_industries(db)
                logger.info("行业分类同步完成，更新 %s 只股票", updated)
        except Exception as e:
            logger.error(f"行业分类同步任务失败: {e}")

        # 每 7 天运行一次
        await asyncio.sleep(7 * 24 * 3600)


async def start_background_tasks():
    """启动所有后台任务"""
    logger.info("启动后台任务...")

    # 启动所有任务
    tasks = [
        asyncio.create_task(seed_stock_list_task()),
        asyncio.create_task(run_anomaly_scan_task()),
        asyncio.create_task(update_industry_benchmarks_task()),
        asyncio.create_task(cleanup_old_alerts_task()),
        asyncio.create_task(sync_industries_task()),
    ]

    # 等待所有任务（理论上不会结束）
    await asyncio.gather(*tasks)