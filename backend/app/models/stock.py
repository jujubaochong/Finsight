"""
股票相关 ORM 模型
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, Boolean, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Stock(Base):
    """股票基础信息"""
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True, comment="股票代码，如 000001")
    name: Mapped[str] = mapped_column(String(50), comment="股票名称")
    market: Mapped[str] = mapped_column(String(4), comment="市场: SZ/SH/BJ")
    industry: Mapped[Optional[str]] = mapped_column(String(50), comment="申万一级行业")
    listing_date: Mapped[Optional[date]] = mapped_column(Date, comment="上市日期")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否正常上市")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    financials = relationship("Financial", back_populates="stock", order_by="Financial.report_period.desc()")
    announcements = relationship("Announcement", back_populates="stock", order_by="Announcement.publish_date.desc()")


class Financial(Base):
    """财务数据（季度/年度）"""
    __tablename__ = "financials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), index=True)
    report_period: Mapped[str] = mapped_column(String(10), comment="报告期，如 2025Q1 / 2024Q4")
    report_type: Mapped[str] = mapped_column(String(4), default="Q", comment="报告类型: Q=季报, Y=年报")

    # 核心财务指标（单位：亿元，比率除外）
    revenue: Mapped[Optional[float]] = mapped_column(Float, comment="营业收入（亿元）")
    net_profit: Mapped[Optional[float]] = mapped_column(Float, comment="净利润（亿元）")
    total_assets: Mapped[Optional[float]] = mapped_column(Float, comment="总资产（亿元）")
    total_equity: Mapped[Optional[float]] = mapped_column(Float, comment="净资产（亿元）")
    operating_cash_flow: Mapped[Optional[float]] = mapped_column(Float, comment="经营活动现金流（亿元）")
    receivables: Mapped[Optional[float]] = mapped_column(Float, comment="应收账款（亿元）")
    inventory: Mapped[Optional[float]] = mapped_column(Float, comment="存货（亿元）")
    goodwill: Mapped[Optional[float]] = mapped_column(Float, comment="商誉（亿元）")
    short_term_borrowing: Mapped[Optional[float]] = mapped_column(Float, comment="短期借款（亿元）")
    total_liability: Mapped[Optional[float]] = mapped_column(Float, comment="总负债（亿元）")
    eps: Mapped[Optional[float]] = mapped_column(Float, comment="每股收益")
    pe_ratio: Mapped[Optional[float]] = mapped_column(Float, comment="市盈率")
    pb_ratio: Mapped[Optional[float]] = mapped_column(Float, comment="市净率")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    stock = relationship("Stock", back_populates="financials")


class Announcement(Base):
    """公司公告"""
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), index=True)
    title: Mapped[str] = mapped_column(String(500), comment="公告标题")
    publish_date: Mapped[date] = mapped_column(Date, index=True, comment="发布日期")
    summary: Mapped[Optional[str]] = mapped_column(Text, comment="AI 摘要")
    url: Mapped[Optional[str]] = mapped_column(String(500), comment="原文链接")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    stock = relationship("Stock", back_populates="announcements")


class Watchlist(Base):
    """用户自选股"""
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", index=True, comment="用户标识")
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalysisReport(Base):
    """AI 生成的报告"""
    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(20), default="standard", comment="standard/quick/deep")
    title: Mapped[str] = mapped_column(String(200), comment="报告标题")
    content: Mapped[str] = mapped_column(Text, comment="报告内容（Markdown）")
    status: Mapped[str] = mapped_column(String(20), default="processing", comment="processing/completed/failed")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class StockAlert(Base):
    """异动提醒记录"""
    __tablename__ = "stock_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", index=True)
    alert_type: Mapped[str] = mapped_column(String(50), comment="异动类型: announcement/shareholder/regulatory/financial")
    severity: Mapped[str] = mapped_column(String(10), default="medium", comment="严重程度: high/medium/low")
    title: Mapped[str] = mapped_column(String(300), comment="异动标题")
    description: Mapped[str] = mapped_column(Text, comment="异动详情")
    source: Mapped[Optional[str]] = mapped_column(String(200), comment="来源（公告标题/URL）")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已读")
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    stock = relationship("Stock")


class IndustryBenchmark(Base):
    """行业基准数据（缓存）"""
    __tablename__ = "industry_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    industry: Mapped[str] = mapped_column(String(50), index=True, comment="申万一级行业")
    report_period: Mapped[str] = mapped_column(String(10), comment="报告期")
    metric_name: Mapped[str] = mapped_column(String(50), comment="指标名称")
    avg_value: Mapped[Optional[float]] = mapped_column(Float, comment="行业均值")
    median_value: Mapped[Optional[float]] = mapped_column(Float, comment="行业中位数")
    max_value: Mapped[Optional[float]] = mapped_column(Float, comment="行业最大值")
    min_value: Mapped[Optional[float]] = mapped_column(Float, comment="行业最小值")
    sample_count: Mapped[int] = mapped_column(Integer, default=0, comment="样本数")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
