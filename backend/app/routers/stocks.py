"""
股票相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import Stock, Watchlist
from app.cache import cache
from app.config import settings
from app.schemas.stock import (
    StockBrief,
    StockSearchResponse,
    StockDetailResponse,
    FinancialItem,
    AnnouncementItem,
    WatchlistItemResponse,
    WatchlistAddRequest,
    WatchlistRemoveResponse,
)
from app.services.data_fetcher import DataFetcher
from app.services.report_generator import ReportGenerator
from app.services.alert_monitor import AlertMonitor

router = APIRouter()


@router.get("/search", response_model=StockSearchResponse)
def search_stocks(q: str, db: Session = Depends(get_db)):
    """模糊搜索股票（纯数据库查询，支持代码/名称/拼音/首字母）"""
    results = DataFetcher.search_stock(db, q)
    return StockSearchResponse(
        query=q,
        results=[StockBrief(**r) for r in results],
        total=len(results),
    )


@router.get("/{code}")
def get_stock_detail(code: str, db: Session = Depends(get_db)):
    """获取股票详情（含财务数据 + 公告 + AI快速分析）"""
    info = DataFetcher.get_stock_detail(db, code)
    if not info:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")

    stock = db.query(Stock).filter(Stock.code == code).first()

    # 财务数据
    financial_raw = DataFetcher.get_financials(db, stock)
    financials = [FinancialItem(**f) for f in financial_raw]

    # 公告
    announcements = [
        AnnouncementItem(
            id=a.id,
            title=a.title,
            publish_date=a.publish_date,
            url=a.url,
        )
        for a in (stock.announcements or [])[:20]
    ]

    # AI 快速分析（带缓存：LLM 调用昂贵且较慢，命中缓存可秒开）
    quick = None
    try:
        qa_key = f"quick_analysis:{code}"
        quick = cache.get(qa_key)
        if quick is None:
            quick = ReportGenerator.generate_quick_analysis(db, code)
            if quick is not None:
                cache.set(qa_key, quick, settings.cache_ttl_analysis)
    except Exception:
        pass  # AI 不可用时静默降级

    return {
        "code": info["code"],
        "name": info["name"],
        "market": info["market"],
        "industry": info["industry"],
        "listing_date": info["listing_date"],
        "is_active": info["is_active"],
        "financials": [f.model_dump() for f in financials],
        "announcements": [a.model_dump() for a in announcements],
        "quick_analysis": quick,
    }


@router.post("/{code}/refresh")
def refresh_stock_data(code: str, db: Session = Depends(get_db)):
    """强制刷新某只股票的数据"""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")
    # 失效缓存，确保拉取最新数据
    cache.delete(f"fin_synced:{code}")
    cache.delete(f"ann_synced:{code}")
    cache.delete(f"quick_analysis:{code}")
    cache.delete("notice_pool")
    # 重新拉取
    DataFetcher._sync_financials(db, stock)
    DataFetcher._sync_announcements(db, stock)
    return {"success": True, "message": f"已刷新 {code} 的数据"}


# ====== 自选股 ======

@router.get("/watchlist/list")
def get_watchlist(user_id: str = "default", db: Session = Depends(get_db)):
    """获取自选股列表"""
    items = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user_id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )
    results = []
    for item in items:
        stock = db.query(Stock).filter(Stock.id == item.stock_id).first()
        if stock:
            alert_count = AlertMonitor.get_stock_alert_count(db, stock.id, user_id)
            results.append(
                WatchlistItemResponse(
                    id=item.id,
                    code=stock.code,
                    name=stock.name,
                    market=stock.market,
                    industry=stock.industry,
                    added_at=item.added_at,
                    has_alert=alert_count > 0,
                )
            )
    return results


@router.post("/watchlist/add")
def add_to_watchlist(req: WatchlistAddRequest, user_id: str = "default", db: Session = Depends(get_db)):
    """添加自选股"""
    stock = db.query(Stock).filter(Stock.code == req.code).first()
    if not stock:
        # 尝试同步
        DataFetcher._sync_stock_list(db)
        stock = db.query(Stock).filter(Stock.code == req.code).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {req.code} 不存在")

    existing = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user_id, Watchlist.stock_id == stock.id)
        .first()
    )
    if existing:
        return {"success": True, "message": "已在自选列表中", "id": existing.id}

    item = Watchlist(user_id=user_id, stock_id=stock.id)
    db.add(item)
    db.commit()
    return {"success": True, "message": "已添加", "id": item.id}


@router.delete("/watchlist/{code}")
def remove_from_watchlist(code: str, user_id: str = "default", db: Session = Depends(get_db)):
    """删除自选股"""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        return WatchlistRemoveResponse(success=False, message="股票不存在")
    item = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user_id, Watchlist.stock_id == stock.id)
        .first()
    )
    if item:
        db.delete(item)
        db.commit()
    return WatchlistRemoveResponse(success=True, message="已移除")
