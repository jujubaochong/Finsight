"""
手动更新示例股票的行业信息
"""
import sys
sys.path.append('.')

from app.database import SessionLocal
from sqlalchemy import func

def update_sample_industries():
    """手动更新示例股票的行业信息"""
    db = SessionLocal()
    
    try:
        from app.models.stock import Stock
        
        # 手动设置的行业信息（基于常识）
        industry_mapping = {
            "000001": "银行",  # 平安银行
            "000002": "房地产",  # 万科A
            "600519": "食品饮料",  # 贵州茅台
            "000858": "食品饮料",  # 五粮液
            "002415": "电子",  # 海康威视
            "000009": "综合",  # 中国宝安
        }
        
        updated_count = 0
        for code, industry in industry_mapping.items():
            stock = db.query(Stock).filter(Stock.code == code).first()
            if stock and (not stock.industry or stock.industry != industry):
                stock.industry = industry
                updated_count += 1
                print(f"更新 {code} {stock.name} 行业为: {industry}")
        
        db.commit()
        print(f"成功更新 {updated_count} 只股票的行业信息")
        
        # 显示更新后的行业分布
        industry_stats = (
            db.query(Stock.industry, func.count(Stock.id))
            .filter(Stock.industry != None)
            .group_by(Stock.industry)
            .order_by(func.count(Stock.id).desc())
            .all()
        )
        
        print("\n当前行业分布:")
        for industry, count in industry_stats:
            print(f"  {industry}: {count} 只股票")
            
    finally:
        db.close()

if __name__ == "__main__":
    update_sample_industries()