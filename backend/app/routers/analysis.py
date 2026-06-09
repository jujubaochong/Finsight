"""
AI 分析相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import Stock
from app.schemas.stock import QuickAnalysisResponse, DeepAnalysisResponse
from app.services.report_generator import ReportGenerator

router = APIRouter()


@router.post("/quick/{code}", response_model=QuickAnalysisResponse)
def quick_analysis(code: str, db: Session = Depends(get_db)):
    """快速分析一只股票"""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")

    result = ReportGenerator.generate_quick_analysis(db, code)
    if not result:
        raise HTTPException(status_code=500, detail="分析生成失败")

    return QuickAnalysisResponse(code=code, analysis=result)


@router.post("/deep/{code}", response_model=DeepAnalysisResponse)
def deep_analysis(
    code: str,
    focus: str = "full",
    user_id: str = "default",
    db: Session = Depends(get_db),
):
    """深度分析 — 触发报告生成（异步）"""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")

    task_id = ReportGenerator.generate_report_async(db, code, user_id, "standard")
    return DeepAnalysisResponse(code=code, task_id=task_id)
