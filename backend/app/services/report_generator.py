"""
报告生成服务 — 编排数据获取 + AI 分析的完整流程
优化点：
  1. 真正的异步执行（使用线程池）
  2. 进度追踪
  3. 报告历史管理
"""
from __future__ import annotations
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.stock import Stock, AnalysisReport
from app.services.data_fetcher import DataFetcher
from app.services.ai_analyzer import deep_analysis, quick_analysis

logger = logging.getLogger(__name__)

# 线程池（限制并发 AI 调用数）
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="report_gen")

# 进度追踪（task_id → progress info）
_task_progress: dict[str, dict] = {}


class ReportGenerator:
    """报告生成编排器"""

    @staticmethod
    def generate_quick_analysis(db: Session, code: str) -> dict | None:
        """为详情页生成快速分析"""
        stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            return None

        stock_info = {
            "name": stock.name,
            "industry": stock.industry or "",
            "market": stock.market,
            "listing_date": str(stock.listing_date) if stock.listing_date else "",
        }
        financials = DataFetcher.get_financials(db, stock)
        announcements = [
            {"title": a.title} for a in (stock.announcements or [])[:10]
        ]

        return quick_analysis(code, stock_info, financials, announcements)

    @staticmethod
    def generate_report_async(
        db: Session,
        code: str,
        user_id: str = "default",
        template: str = "standard",
    ) -> str:
        """
        异步生成完整研究报告
        返回 task_id（即 report_id）
        """
        stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            raise ValueError(f"股票 {code} 不存在")

        # 创建报告记录（processing 状态）
        report = AnalysisReport(
            user_id=user_id,
            stock_id=stock.id,
            report_type=template,
            title=f"{stock.name}({stock.code}) 研究报告",
            content="",
            status="processing",
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        task_id = str(report.id)

        # 初始化进度
        _task_progress[task_id] = {
            "status": "processing",
            "progress": 10,
            "message": "正在准备数据...",
            "current_step": "data_fetch",
        }

        # 提交到线程池异步执行
        _executor.submit(
            ReportGenerator._do_generate,
            task_id,
            code,
            stock.id,
            stock.name,
            stock.industry or "",
            stock.market,
            str(stock.listing_date) if stock.listing_date else "",
        )

        logger.info(f"报告生成任务已提交: task_id={task_id}, code={code}")
        return task_id

    @staticmethod
    def _do_generate(
        task_id: str,
        code: str,
        stock_id: int,
        name: str,
        industry: str,
        market: str,
        listing_date: str,
    ):
        """在后台线程中执行报告生成"""
        db = SessionLocal()
        try:
            stock = db.query(Stock).filter(Stock.id == stock_id).first()
            if not stock:
                raise ValueError(f"Stock not found: {stock_id}")

            # Step 1: 获取数据
            _task_progress[task_id] = {
                "status": "processing",
                "progress": 20,
                "message": "正在获取财务数据...",
                "current_step": "data_fetch",
            }

            stock_info = {
                "name": name,
                "industry": industry,
                "market": market,
                "listing_date": listing_date,
                "code": code,
            }
            financials = DataFetcher.get_financials(db, stock)

            _task_progress[task_id] = {
                "status": "processing",
                "progress": 40,
                "message": "正在分析财务趋势...",
                "current_step": "ai_analysis",
            }

            announcements = [
                {"title": a.title} for a in (stock.announcements or [])[:15]
            ]

            # Step 2: AI 生成报告
            _task_progress[task_id] = {
                "status": "processing",
                "progress": 60,
                "message": "AI 正在撰写报告...",
                "current_step": "ai_writing",
            }

            content = deep_analysis(code, stock_info, financials, announcements)

            _task_progress[task_id] = {
                "status": "processing",
                "progress": 90,
                "message": "正在保存报告...",
                "current_step": "saving",
            }

            # Step 3: 保存结果
            report = db.query(AnalysisReport).filter(AnalysisReport.id == int(task_id)).first()
            if report:
                report.content = content
                report.status = "completed"
                db.commit()

            _task_progress[task_id] = {
                "status": "completed",
                "progress": 100,
                "message": "报告已生成",
                "current_step": "done",
            }

            logger.info(f"报告生成完成: task_id={task_id}, code={code}")

        except Exception as e:
            logger.error(f"报告生成失败: task_id={task_id}, error={e}", exc_info=True)

            _task_progress[task_id] = {
                "status": "failed",
                "progress": 0,
                "message": f"生成失败: {str(e)[:100]}",
                "current_step": "error",
            }

            # 更新数据库状态
            try:
                report = db.query(AnalysisReport).filter(AnalysisReport.id == int(task_id)).first()
                if report:
                    report.status = "failed"
                    report.content = f"报告生成失败：{e}"
                    db.commit()
            except Exception:
                pass

        finally:
            db.close()

    @staticmethod
    def get_task_progress(task_id: str) -> dict:
        """获取任务进度"""
        return _task_progress.get(task_id, {
            "status": "unknown",
            "progress": 0,
            "message": "任务不存在",
        })

    @staticmethod
    def get_report(db: Session, report_id: int) -> AnalysisReport | None:
        return db.query(AnalysisReport).filter(AnalysisReport.id == report_id).first()

    @staticmethod
    def get_reports_by_stock(
        db: Session, code: str, user_id: str = "default"
    ) -> list[AnalysisReport]:
        stock = db.query(Stock).filter(Stock.code == code).first()
        if not stock:
            return []
        return (
            db.query(AnalysisReport)
            .filter(
                AnalysisReport.stock_id == stock.id,
                AnalysisReport.user_id == user_id,
            )
            .order_by(AnalysisReport.created_at.desc())
            .all()
        )

    @staticmethod
    def get_all_reports(db: Session, user_id: str = "default") -> list[AnalysisReport]:
        """获取用户的所有报告"""
        return (
            db.query(AnalysisReport)
            .filter(AnalysisReport.user_id == user_id)
            .order_by(AnalysisReport.created_at.desc())
            .limit(50)
            .all()
        )
