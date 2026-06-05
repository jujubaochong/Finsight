"""
FinSight FastAPI 应用入口
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import engine
from app.models.stock import Base
from app.routers import stocks, analysis, reports, alerts, industry
from app.logger import setup_logging
from app.background_tasks import start_background_tasks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()
    logger.info("FinSight API 启动中...")

    # 创建数据库表
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已就绪")

    # 启动时预加载数据
    try:
        from app.database import SessionLocal
        from app.services.industry_analyzer import IndustryAnalyzer
        from app.services.alert_monitor import AlertMonitor
        
        db = SessionLocal()
        try:
            # 初始化行业基准数据
            logger.info("初始化行业基准数据...")
            IndustryAnalyzer.update_all_industry_benchmarks(db)
            logger.info("行业基准数据初始化完成")
            
            # 运行一次异常扫描
            logger.info("执行初始异常扫描...")
            alerts = AlertMonitor.scan_watchlist_alerts(db)
            logger.info(f"初始异常扫描完成，发现 {len(alerts)} 个异常")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"启动初始化失败（不影响应用启动）: {e}")

    # 启动后台任务
    task = asyncio.create_task(start_background_tasks())

    yield

    # 关闭时取消后台任务
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("后台任务已取消")

    logger.info("FinSight API 关闭")


app = FastAPI(
    title="FinSight API",
    version="0.2.0",
    description="AI 驱动的智能投研平台 — 后端 API",
    lifespan=lifespan,
)

# CORS — 允许本地开发和部署后的域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


# 注册路由
app.include_router(stocks.router, prefix="/api/stocks", tags=["股票"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["AI分析"])
app.include_router(reports.router, prefix="/api/reports", tags=["报告"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["异动监控"])
app.include_router(industry.router, prefix="/api/industry", tags=["行业对标"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/stats")
async def stats():
    """简易统计（开发调试用）"""
    from app.database import SessionLocal
    from app.models.stock import Stock, AnalysisReport

    db = SessionLocal()
    try:
        stock_count = db.query(Stock).count()
        report_count = db.query(AnalysisReport).count()
        return {
            "stocks_in_db": stock_count,
            "reports_generated": report_count,
        }
    finally:
        db.close()
