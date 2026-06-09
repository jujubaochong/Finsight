"""
填充股票行业分类数据脚本

用法：python scripts/populate_industries.py

复用 DataFetcher._sync_industries（申万一级行业 + 成分股映射）填充
Stock.industry，并可选地添加示例自选股用于测试异动监控。
"""
import logging
import sys

from sqlalchemy import func

sys.path.append(".")
from app.database import SessionLocal
from app.models.stock import Stock, Watchlist
from app.services.data_fetcher import DataFetcher

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def populate_industry_data() -> bool:
    """从 AkShare 获取申万一级行业分类并更新数据库"""
    logger.info("开始获取股票行业分类数据...")
    db = SessionLocal()
    try:
        # 确保股票列表存在（行业映射依赖股票列表）
        DataFetcher._sync_stock_list(db)
        updated = DataFetcher._sync_industries(db, force=True)
        logger.info("行业分类数据填充完成，共更新 %s 条记录", updated)

        # 统计行业分布
        industry_stats = (
            db.query(Stock.industry, func.count(Stock.id))
            .filter(Stock.industry.isnot(None))
            .group_by(Stock.industry)
            .order_by(func.count(Stock.id).desc())
            .all()
        )
        logger.info("行业分布统计（前 10）：")
        for industry, count in industry_stats[:10]:
            logger.info("  %s: %s 只股票", industry, count)
        return updated > 0
    except Exception as e:  # noqa: BLE001
        logger.error("填充行业数据失败: %s", e)
        return False
    finally:
        db.close()


def add_sample_watchlist():
    """添加示例自选股，用于测试异动监控"""
    logger.info("添加示例自选股...")
    sample_stocks = ["000001", "000002", "600519", "000858", "002415"]

    db = SessionLocal()
    try:
        added_count = 0
        for code in sample_stocks:
            stock = db.query(Stock).filter(Stock.code == code).first()
            if not stock:
                continue
            existing = (
                db.query(Watchlist)
                .filter(Watchlist.user_id == "default", Watchlist.stock_id == stock.id)
                .first()
            )
            if not existing:
                db.add(Watchlist(user_id="default", stock_id=stock.id))
                added_count += 1
                logger.info("添加自选股: %s %s", code, stock.name)
        db.commit()
        logger.info("添加了 %s 只示例自选股", added_count)
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=== FinSight 数据填充脚本 ===")
    if populate_industry_data():
        logger.info("行业数据填充成功")
    else:
        logger.warning("行业数据填充失败，但将继续运行")
    add_sample_watchlist()
    logger.info("数据填充脚本执行完成")
