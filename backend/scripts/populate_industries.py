"""
填充股票行业分类数据脚本
使用 AkShare 获取股票行业信息并更新数据库
"""
import sys
import logging
from datetime import datetime

# 添加项目路径
sys.path.append('.')
from app.database import SessionLocal, engine
from app.models.stock import Stock
import akshare as ak

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_industry_data():
    """从 AkShare 获取行业分类并更新数据库"""
    logger.info("开始获取股票行业分类数据...")
    
    try:
        # 尝试获取新浪行业分类数据
        df = ak.stock_sector_spot(indicator="新浪行业")
        
        if df is None or df.empty:
            logger.warning("无法获取新浪行业分类数据，尝试其他接口...")
            # 尝试获取申万行业分类
            df = ak.stock_sector_spot(indicator="申万一级行业")
            
        if df is None or df.empty:
            logger.error("无法获取任何行业分类数据")
            return False
        
        logger.info(f"获取到 {len(df)} 条行业分类数据")
        
        db = SessionLocal()
        updated_count = 0
        
        try:
            # 遍历数据并更新数据库
            for _, row in df.iterrows():
                code = str(row.get('代码', '')).strip()
                name = str(row.get('名称', '')).strip()
                industry = str(row.get('所属行业', '')).strip()
                
                if not code or not industry:
                    continue
                    
                # 查找数据库中的股票
                stock = db.query(Stock).filter(Stock.code == code).first()
                if stock and not stock.industry:
                    stock.industry = industry
                    updated_count += 1
                    
                    # 每100条提交一次
                    if updated_count % 100 == 0:
                        db.commit()
                        logger.info(f"已更新 {updated_count} 条记录")
            
            # 最终提交
            db.commit()
            logger.info(f"行业分类数据填充完成，共更新 {updated_count} 条记录")
            
            # 统计行业分布
            industry_stats = (
                db.query(Stock.industry, db.func.count(Stock.id))
                .filter(Stock.industry != None)
                .group_by(Stock.industry)
                .order_by(db.func.count(Stock.id).desc())
                .all()
            )
            
            logger.info("行业分布统计:")
            for industry, count in industry_stats[:10]:  # 只显示前10个行业
                logger.info(f"  {industry}: {count} 只股票")
                
        finally:
            db.close()
            
        return True
        
    except Exception as e:
        logger.error(f"填充行业数据失败: {e}")
        return False

def add_sample_watchlist():
    """添加示例自选股，用于测试异动监控"""
    logger.info("添加示例自选股...")
    
    sample_stocks = [
        "000001",  # 平安银行
        "000002",  # 万科A
        "600519",  # 贵州茅台
        "000858",  # 五粮液
        "002415",  # 海康威视
    ]
    
    db = SessionLocal()
    try:
        from app.models.stock import Watchlist
        
        added_count = 0
        for code in sample_stocks:
            stock = db.query(Stock).filter(Stock.code == code).first()
            if stock:
                # 检查是否已存在
                existing = db.query(Watchlist).filter(
                    Watchlist.user_id == "default",
                    Watchlist.stock_id == stock.id
                ).first()
                
                if not existing:
                    watchlist_item = Watchlist(
                        user_id="default",
                        stock_id=stock.id
                    )
                    db.add(watchlist_item)
                    added_count += 1
                    logger.info(f"添加自选股: {code} {stock.name}")
        
        db.commit()
        logger.info(f"添加了 {added_count} 只示例自选股")
        
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("=== FinSight 数据填充脚本 ===")
    
    # 填充行业数据
    if populate_industry_data():
        logger.info("行业数据填充成功")
    else:
        logger.warning("行业数据填充失败，但将继续运行")
    
    # 添加示例自选股
    add_sample_watchlist()
    
    logger.info("数据填充脚本执行完成")