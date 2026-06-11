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

    同步 ``def``：由 FastAPI 线程池执行，避免阻塞事件循环。

    刷新分两条路径，确保接口本身不会超过前端超时：
      - 财务数据：单只股票的【定向】查询，已被单次调用超时（12s）兜底，
        因此同步刷新，刷新返回时前端即可见最新财务数据。
      - 公告：需要抓取【全市场】单日公告（最重的一步，时间预算可达 ~130s，
        远超前端 60s 超时），改为**后台异步**刷新——若仍同步执行，刷新接口
        会和详情页一样卡死/超时。新公告会在后台同步完成后，于下次进入详情或
        再次刷新时可见。
    """
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")
    # 失效缓存，确保拉取最新数据。
    # 注意：不删除 ``ann_syncing:{code}``——若已有后台公告同步在进行中，
    # 本次刷新让 _trigger_announcements_sync_async 自然成为 no-op，
    # 避免重复触发【全市场】公告抓取（很重）造成并发浪费。
    cache.delete(f"fin_synced:{code}")
    cache.delete(f"ann_synced:{code}")
    cache.delete("notice_pool")
    # 财务：同步刷新（定向查询，受单次调用超时兜底）
    DataFetcher._sync_financials(db, stock)
    # 公告：后台异步刷新（全市场抓取很重，不放在请求路径上，避免超时）
    DataFetcher._trigger_announcements_sync_async(code)
    return {
        "success": True,
        "message": f"已刷新 {code} 的财务数据，公告正在后台更新",
    }


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
