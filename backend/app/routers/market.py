"""
行情/技术面/资金面 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import Stock
from app.services.market_data import get_market_snapshot
from app.services.ai_analyzer import short_term_analysis

router = APIRouter()


@router.get("/snapshot/{code}")
def market_snapshot(code: str, lhb: bool = False, db: Session = Depends(get_db)):
    """技术面 + 资金面快照（K线指标、MACD/KDJ/RSI、主力资金流，可选龙虎榜）

    同步 def：内部并行抓取 K线与资金流，交由 FastAPI 线程池执行，不阻塞事件循环。
    """
    snap = get_market_snapshot(code, include_lhb=lhb)
    return snap


@router.post("/short-term/{code}")
def short_term_research(code: str, db: Session = Depends(get_db)):
    """AI 短线研判：结合 K线形态/MACD/资金流/龙虎榜，输出机会与风险

    用短线交易语言（吸筹/承接/出货/炸板等）解读，仅供参考、不构成投资建议。
    """
    stock = db.query(Stock).filter(Stock.code == code).first()
    name = stock.name if stock else code
    industry = (stock.industry if stock else "") or ""

    snap = get_market_snapshot(code, include_lhb=True)
    if not snap.get("indicators") and not snap.get("fund_flow"):
        raise HTTPException(status_code=503, detail="行情数据暂时不可用，请稍后重试")

    result = short_term_analysis(code, name, industry, snap)
    return {"code": code, "name": name, "analysis": result}
