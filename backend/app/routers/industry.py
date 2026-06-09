"""
行业对标分析 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.industry_analyzer import IndustryAnalyzer

router = APIRouter()


@router.get("/comparison/{code}")
def get_industry_comparison(code: str, db: Session = Depends(get_db)):
    """获取行业对标分析数据"""
    result = IndustryAnalyzer.get_industry_comparison(db, code)
    if "error" in result and "target_metrics" not in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/list")
def get_industry_list(db: Session = Depends(get_db)):
    """获取所有行业列表"""
    return IndustryAnalyzer.get_industry_list(db)


@router.get("/peers/{code}")
def get_industry_peers(code: str, limit: int = 20, db: Session = Depends(get_db)):
    """获取同行业股票列表"""
    peers = IndustryAnalyzer.get_industry_peers(db, code, limit)
    return {"code": code, "peers": peers, "count": len(peers)}
