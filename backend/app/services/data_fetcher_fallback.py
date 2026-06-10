"""
财务数据降级方案 - 当 AkShare 不可用时提供模拟数据
"""
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from sqlalchemy.orm import Session

from app.models.stock import Financial

logger = logging.getLogger(__name__)


class DataFetcherFallback:
    """财务数据降级方案（当 AkShare 不可用时使用）"""
    
    @staticmethod
    def generate_mock_financials(db: Session, stock_id: int, stock_code: str, stock_name: str) -> List[Dict]:
        """生成模拟财务数据
        
        基于股票代码和名称生成合理的模拟数据，用于演示和测试
        """
        logger.info(f"为 {stock_code} {stock_name} 生成模拟财务数据")
        
        # 基于股票代码和名称生成一些合理的模拟数据
        financials = []
        base_year = datetime.now().year - 1
        
        # 生成最近4个季度的数据
        for i in range(4):
            year = base_year
            quarter = 4 - i
            
            # 调整年份和季度
            if quarter <= 0:
                year -= 1
                quarter = 4 + quarter
            
            period = f"{year}Q{quarter}"
            
            # 根据股票类型生成不同的基础值
            if "银行" in stock_name or stock_code.startswith("000001"):
                # 银行股
                base_revenue = 30.0 + random.uniform(-5, 10)
                base_profit = 10.0 + random.uniform(-2, 4)
                base_assets = 4000.0 + random.uniform(-500, 800)
            elif "茅台" in stock_name or "五粮液" in stock_name:
                # 白酒股
                base_revenue = 80.0 + random.uniform(-10, 20)
                base_profit = 40.0 + random.uniform(-5, 10)
                base_assets = 200.0 + random.uniform(-30, 50)
            elif "房地产" in stock_name or "万科" in stock_name:
                # 房地产股
                base_revenue = 50.0 + random.uniform(-10, 15)
                base_profit = 5.0 + random.uniform(-1, 2)
                base_assets = 2000.0 + random.uniform(-300, 500)
            else:
                # 其他股票
                base_revenue = 10.0 + random.uniform(-3, 6)
                base_profit = 1.0 + random.uniform(-0.3, 0.6)
                base_assets = 100.0 + random.uniform(-20, 30)
            
            # 添加季节性和增长趋势
            revenue = base_revenue * (1 + 0.05 * i) * (0.9 + 0.1 * random.random())
            net_profit = base_profit * (1 + 0.08 * i) * (0.85 + 0.15 * random.random())
            total_assets = base_assets * (1 + 0.03 * i) * (0.95 + 0.05 * random.random())
            total_equity = total_assets * 0.4 * (0.9 + 0.1 * random.random())
            operating_cash_flow = net_profit * 1.2 * (0.8 + 0.4 * random.random())
            
            financial_data = {
                "stock_id": stock_id,
                "report_period": period,
                "report_type": "Y" if quarter == 4 else "Q",
                "revenue": round(revenue, 2),
                "net_profit": round(net_profit, 2),
                "total_assets": round(total_assets, 2),
                "total_equity": round(total_equity, 2),
                "operating_cash_flow": round(operating_cash_flow, 2),
                "receivables": round(revenue * 0.3 * random.uniform(0.8, 1.2), 2),
                "inventory": round(revenue * 0.2 * random.uniform(0.7, 1.3), 2),
                "eps": round(net_profit / 10 * random.uniform(0.8, 1.2), 2),
                "pe_ratio": round(random.uniform(8, 30), 2),
                "pb_ratio": round(random.uniform(0.8, 3), 2),
            }
            
            financials.append(financial_data)
        
        return financials
    
    @staticmethod
    def save_mock_financials(db: Session, stock_id: int, financials: List[Dict]) -> int:
        """保存模拟财务数据到数据库"""
        saved_count = 0
        
        for fin_data in financials:
            # 检查是否已存在
            existing = db.query(Financial).filter(
                Financial.stock_id == stock_id,
                Financial.report_period == fin_data["report_period"],
            ).first()
            
            if not existing:
                fin = Financial(**fin_data)
                db.add(fin)
                saved_count += 1
        
        try:
            db.commit()
            logger.info(f"保存了 {saved_count} 条模拟财务数据")
            return saved_count
        except Exception as e:
            db.rollback()
            logger.error(f"保存模拟财务数据失败: {e}")
            return 0
    
    @staticmethod
    def generate_mock_announcements(stock_code: str, stock_name: str) -> List[Dict]:
        """生成模拟公告数据"""
        announcements = []
        base_date = datetime.now().date()
        
        announcement_templates = [
            f"{stock_name}发布年度报告",
            f"{stock_name}发布半年度报告",
            f"{stock_name}发布季度报告",
            f"{stock_name}业绩预告",
            f"{stock_name}股东持股变动公告",
            f"{stock_name}董事会决议公告",
            f"{stock_name}重大合同公告",
            f"{stock_name}关联交易公告",
        ]
        
        for i in range(min(5, len(announcement_templates))):
            publish_date = base_date - timedelta(days=30 * i)
            title = announcement_templates[i]
            
            announcements.append({
                "title": title,
                "publish_date": publish_date,
                "url": "",  # 模拟数据无真实链接，前端据此不展示"查看原文"
            })
        
        return announcements