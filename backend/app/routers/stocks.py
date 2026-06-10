"""
股票相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import Stock, Watchlist
from app.cache import cache
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
from app.services.alert_monitor import AlertMonitor

router = APIRouter()


@router.get("/search", response_model=StockSearchResponse)
def search_stocks(q: str, db: Session = Depends(get_db)):
    """模糊搜索股票

    定义为同步 ``def``：FastAPI 会在工作线程池中执行，避免（即便很快的）
    数据库查询阻塞事件循环。搜索本身只查数据库，不会触发慢速网络下载。
    """
    results = DataFetcher.search_stock(db, q)
    return StockSearchResponse(
        query=q,
        results=[StockBrief(**r) for r in results],
        total=len(results),
    )


@router.get("/{code}")
def get_stock_detail(code: str, db: Session = Depends(get_db)):
    """获取股票详情（含财务数据 + 公告 + AI快速分析）

    定义为同步 ``def``：详情会触发 akshare 财务/公告同步与 AI 调用等阻塞操作，
    交给 FastAPI 线程池执行，避免阻塞事件循环（否则会把同时进行的搜索也卡死）。
    """
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

    # AI 快速分析不再内联生成（它是最慢、最易失败的一环）。
    # 前端在详情加载完成后单独调用 POST /analysis/quick/{code} 异步获取，
    # 各自带 loading 状态，避免拖慢首屏。
    return {
        "code": info["code"],
        "name": info["name"],
        "market": info["market"],
        "industry": info["industry"],
        "listing_date": info["listing_date"],
        "is_active": info["is_active"],
        "financials": [f.model_dump() for f in financials],
        "announcements": [a.model_dump() for a in announcements],
        "quick_analysis": None,
    }


@router.post("/{code}/refresh")
def refresh_stock_data(code: str, db: Session = Depends(get_db)):
    """强制刷新某只股票的数据

    同步 ``def``：刷新会逐项重新拉取 akshare 财务与公告数据（阻塞），由线程池执行，
    避免阻塞事件循环。配合 data_fetcher 中的单次调用超时与公告抓取时间预算，
    刷新会在有限时间内返回（即使部分数据源不可用也会降级而非卡死）。
    """
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")
    # 失效缓存，确保拉取最新数据
    cache.delete(f"fin_synced:{code}")
    cache.delete(f"ann_synced:{code}")
    cache.delete("notice_pool")
    # 重新拉取
    DataFetcher._sync_financials(db, stock)
    DataFetcher._sync_announcements(db, stock)
    return {"success": True, "message": f"已刷新 {code} 的数据"}


# ====== 自选股 ======

@router.get("/watchlist/list")
async def get_watchlist(user_id: str = "default", db: Session = Depends(get_db)):
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
async def add_to_watchlist(req: WatchlistAddRequest, user_id: str = "default", db: Session = Depends(get_db)):
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
async def remove_from_watchlist(code: str, user_id: str = "default", db: Session = Depends(get_db)):
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
