"""
报告相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.stock import AnalysisReport
from app.schemas.stock import (
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportStatusResponse,
    ReportResponse,
    ReportListItem,
)
from app.services.report_generator import ReportGenerator

router = APIRouter()


@router.post("/generate/{code}", response_model=ReportGenerateResponse)
async def generate_report(
    code: str,
    req: ReportGenerateRequest = ReportGenerateRequest(),
    user_id: str = "default",
    db: Session = Depends(get_db),
):
    """生成个股研究报告（异步）"""
    try:
        task_id = ReportGenerator.generate_report_async(db, code, user_id, req.template)
        return ReportGenerateResponse(code=code, task_id=task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/status/{task_id}", response_model=ReportStatusResponse)
async def get_report_status(task_id: str, db: Session = Depends(get_db)):
    """查询报告生成状态（支持实时进度）"""
    try:
        report_id = int(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的任务ID")

    # 优先从进度追踪获取（更实时）
    progress_info = ReportGenerator.get_task_progress(task_id)
    if progress_info["status"] != "unknown":
        report = ReportGenerator.get_report(db, report_id)
        return ReportStatusResponse(
            task_id=task_id,
            status=progress_info["status"],
            title=report.title if report else "",
            progress=progress_info["progress"],
            message=progress_info["message"],
        )

    # 降级从数据库查
    report = ReportGenerator.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return ReportStatusResponse(
        task_id=task_id,
        status=report.status,
        title=report.title,
        progress=100 if report.status == "completed" else 50,
        message="报告已生成" if report.status == "completed" else "生成中...",
    )


@router.get("/list")
async def list_reports(user_id: str = "default", db: Session = Depends(get_db)):
    """获取用户的报告列表"""
    reports = ReportGenerator.get_all_reports(db, user_id)
    return [
        ReportListItem(
            report_id=r.id,
            title=r.title,
            report_type=r.report_type,
            status=r.status,
            created_at=r.created_at,
        ).model_dump()
        for r in reports
    ]


@router.get("/{report_id}")
async def get_report(report_id: int, db: Session = Depends(get_db)):
    """获取报告内容"""
    report = ReportGenerator.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return ReportResponse(
        report_id=report.id,
        title=report.title,
        content=report.content,
        report_type=report.report_type,
        status=report.status,
        created_at=report.created_at,
    )


@router.get("/{report_id}/export")
async def export_report(
    report_id: int, format: str = "markdown", db: Session = Depends(get_db)
):
    """导出报告"""
    report = ReportGenerator.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if report.status != "completed":
        raise HTTPException(status_code=400, detail="报告尚未生成完成")

    if format in ("markdown", "md"):
        return PlainTextResponse(
            content=report.content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=report_{report_id}.md"
            },
        )
    return PlainTextResponse(
        content=report.content, media_type="text/plain; charset=utf-8"
    )


@router.delete("/{report_id}")
async def delete_report(report_id: int, db: Session = Depends(get_db)):
    """删除报告"""
    report = ReportGenerator.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(report)
    db.commit()
    return {"success": True, "message": "报告已删除"}
