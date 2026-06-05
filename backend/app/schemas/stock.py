"""
Pydantic 请求/响应模型
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


# ====== 股票搜索 ======

class StockBrief(BaseModel):
    code: str
    name: str
    market: str
    industry: Optional[str] = None

    class Config:
        from_attributes = True


class StockSearchResponse(BaseModel):
    query: str
    results: list[StockBrief]
    total: int = 0


# ====== 股票详情 ======

class FinancialItem(BaseModel):
    report_period: str
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    total_assets: Optional[float] = None
    total_equity: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    receivables: Optional[float] = None
    inventory: Optional[float] = None
    eps: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None

    # 计算字段
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    debt_ratio: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    profit_growth_yoy: Optional[float] = None


class AnnouncementItem(BaseModel):
    id: int
    title: str
    publish_date: date
    summary: Optional[str] = None
    url: Optional[str] = None


class QuickAnalysisResult(BaseModel):
    summary: str
    strengths: list[str] = []
    risks: list[str] = []
    metrics_commentary: str = ""


class StockDetailResponse(BaseModel):
    code: str
    name: str
    market: str
    industry: Optional[str] = None
    listing_date: Optional[date] = None
    is_active: bool = True
    financials: list[FinancialItem] = []
    announcements: list[AnnouncementItem] = []
    quick_analysis: Optional[QuickAnalysisResult] = None


# ====== AI 分析 ======

class QuickAnalysisResponse(BaseModel):
    code: str
    analysis: dict  # 灵活接受 AI 返回的结构


class DeepAnalysisRequest(BaseModel):
    focus: str = "full"  # full / financial / risk


class DeepAnalysisResponse(BaseModel):
    code: str
    task_id: str


# ====== 报告 ======

class ReportGenerateRequest(BaseModel):
    template: str = "standard"


class ReportGenerateResponse(BaseModel):
    code: str
    task_id: str


class ReportStatusResponse(BaseModel):
    task_id: str
    status: str  # processing / completed / failed
    title: Optional[str] = None
    progress: int = 0
    message: str = ""


class ReportResponse(BaseModel):
    report_id: int
    title: str
    content: str
    report_type: str
    status: str
    created_at: datetime


class ReportListItem(BaseModel):
    report_id: int
    title: str
    report_type: str
    status: str
    created_at: datetime


# ====== 自选股 ======

class WatchlistItemResponse(BaseModel):
    id: int
    code: str
    name: str
    market: str
    industry: Optional[str] = None
    added_at: datetime
    quick_summary: Optional[str] = None
    has_alert: bool = False


class WatchlistAddRequest(BaseModel):
    code: str


class WatchlistRemoveResponse(BaseModel):
    success: bool
    message: str
