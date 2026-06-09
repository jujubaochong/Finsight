"""
异动监控 API 路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.alert_monitor import AlertMonitor

router = APIRouter()


@router.get("/list")
def get_alerts(
    user_id: str = "default",
    unread_only: bool = False,
    stock_code: str = None,
    db: Session = Depends(get_db),
):
    """获取异动提醒列表"""
    alerts = AlertMonitor.get_alerts(db, user_id, unread_only, stock_code)
    return [
        {
            "id": a.id,
            "stock_code": a.stock.code if a.stock else "",
            "stock_name": a.stock.name if a.stock else "",
            "alert_type": a.alert_type,
            "severity": a.severity,
            "title": a.title,
            "description": a.description,
            "is_read": a.is_read,
            "detected_at": a.detected_at.isoformat(),
        }
        for a in alerts
    ]


@router.post("/scan")
def scan_alerts(user_id: str = "default", db: Session = Depends(get_db)):
    """手动触发异动扫描"""
    results = AlertMonitor.scan_watchlist_alerts(db, user_id)
    return {
        "success": True,
        "new_alerts": len(results),
        "alerts": results,
    }


@router.post("/read/{alert_id}")
def mark_read(alert_id: int, user_id: str = "default", db: Session = Depends(get_db)):
    """标记异动为已读"""
    success = AlertMonitor.mark_alert_read(db, alert_id, user_id)
    return {"success": success}


@router.post("/read-all")
def mark_all_read(user_id: str = "default", db: Session = Depends(get_db)):
    """标记所有异动为已读"""
    AlertMonitor.mark_all_read(db, user_id)
    return {"success": True}


@router.get("/count")
def get_unread_count(user_id: str = "default", db: Session = Depends(get_db)):
    """获取未读异动数"""
    alerts = AlertMonitor.get_alerts(db, user_id, unread_only=True)
    return {"unread_count": len(alerts)}
