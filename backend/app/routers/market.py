"""
行情/技术面/资金面 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import Stock
from app.services.market_data import get_market_snapshot, get_market_overview
from app.services.ai_analyzer import short_term_analysis, decision_analysis
from app.services.data_fetcher import DataFetcher

router = APIRouter()


class ExpectationRequest(BaseModel):
    direction: str = "unsure"  # bullish / bearish / unsure
    horizon: str = "unsure"    # long / short / unsure


@router.get("/overview")
def market_overview():
    """首页市场概览：行业板块涨跌 + 主力净流入潜力股（并行抓取，带缓存）"""
    return get_market_overview()


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


@router.get("/decision/{code}")
def decision_snapshot(code: str, db: Session = Depends(get_db)):
    """决策对照台 - 客观数据部分（风险收益 + 关键指标），不含AI、秒出。"""
    snap = get_market_snapshot(code, include_lhb=False)
    return {
        "code": code,
        "latest": snap.get("latest", {}),
        "risk_reward": snap.get("risk_reward", {}),
        "main_phase": snap.get("main_phase", {}),
        "fund_flow": {k: v for k, v in snap.get("fund_flow", {}).items() if k != "series"},
    }


@router.post("/decision/{code}")
def decision_compare(code: str, exp: ExpectationRequest, db: Session = Depends(get_db)):
    """决策对照台 - AI 部分：长短线倾向 + 风险收益解读 + 与用户预期对照。

    用户先提交自己的预期（方向/周期），AI 给出独立判断并指出一致或分歧，
    用于"对照自己的想法"，而非替用户决策。
    """
    stock = db.query(Stock).filter(Stock.code == code).first()
    name = stock.name if stock else code
    industry = (stock.industry if stock else "") or ""

    snap = get_market_snapshot(code, include_lhb=True)
    if not snap.get("indicators") and not snap.get("fund_flow"):
        raise HTTPException(status_code=503, detail="行情数据暂时不可用，请稍后重试")

    financials = []
    if stock:
        try:
            financials = DataFetcher.get_financials(db, stock, fetch_if_missing=False)
        except Exception:  # noqa: BLE001
            financials = []

    result = decision_analysis(
        code, name, industry, snap, financials,
        user_expectation={"direction": exp.direction, "horizon": exp.horizon},
    )
    return {"code": code, "name": name, "decision": result, "risk_reward": snap.get("risk_reward", {})}
