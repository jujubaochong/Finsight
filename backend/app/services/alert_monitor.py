"""
异动监控服务 — 检测自选股的重要变化并生成提醒
规则引擎 + 公告关键词匹配
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.stock import Stock, Announcement, Watchlist, StockAlert, Financial

logger = logging.getLogger(__name__)


# ========== 异动规则定义 ==========

# 公告关键词规则
ANNOUNCEMENT_RULES = [
    # (关键词列表, 异动类型, 严重程度, 描述模板)
    {
        "keywords": ["年报", "年度报告"],
        "type": "announcement",
        "severity": "high",
        "template": "发布年度报告",
    },
    {
        "keywords": ["半年报", "半年度报告"],
        "type": "announcement",
        "severity": "high",
        "template": "发布半年度报告",
    },
    {
        "keywords": ["季报", "季度报告", "第一季度", "第三季度"],
        "type": "announcement",
        "severity": "high",
        "template": "发布季度报告",
    },
    {
        "keywords": ["业绩预告", "业绩快报"],
        "type": "announcement",
        "severity": "high",
        "template": "发布业绩预告/快报",
    },
    {
        "keywords": ["业绩预增", "业绩预减", "业绩预亏", "业绩预盈"],
        "type": "announcement",
        "severity": "high",
        "template": "业绩预告（关注变化方向）",
    },
    {
        "keywords": ["减持", "股东减持"],
        "type": "shareholder",
        "severity": "high",
        "template": "大股东减持公告",
    },
    {
        "keywords": ["增持", "股东增持"],
        "type": "shareholder",
        "severity": "medium",
        "template": "大股东增持公告",
    },
    {
        "keywords": ["实际控制人变更", "控制权变更"],
        "type": "shareholder",
        "severity": "high",
        "template": "实际控制人/控制权变更",
    },
    {
        "keywords": ["问询函", "关注函", "监管函"],
        "type": "regulatory",
        "severity": "high",
        "template": "收到交易所问询/关注函",
    },
    {
        "keywords": ["立案调查", "行政处罚"],
        "type": "regulatory",
        "severity": "high",
        "template": "被立案调查或行政处罚",
    },
    {
        "keywords": ["重大诉讼", "仲裁"],
        "type": "regulatory",
        "severity": "medium",
        "template": "涉及重大诉讼/仲裁",
    },
    {
        "keywords": ["资产重组", "重大资产购买", "重大资产出售"],
        "type": "announcement",
        "severity": "high",
        "template": "重大资产重组公告",
    },
    {
        "keywords": ["股权质押", "质押"],
        "type": "shareholder",
        "severity": "medium",
        "template": "股权质押相关公告",
    },
    {
        "keywords": ["董事辞职", "监事辞职", "高管辞职", "总经理辞职"],
        "type": "announcement",
        "severity": "medium",
        "template": "董监高辞职公告",
    },
    {
        "keywords": ["分红", "利润分配", "派息"],
        "type": "announcement",
        "severity": "low",
        "template": "利润分配/分红方案",
    },
]

# 财务异动规则（基于数据变化）
FINANCIAL_RULES = [
    {
        "metric": "revenue_growth_yoy",
        "condition": "less_than",
        "threshold": -20,
        "type": "financial",
        "severity": "high",
        "template": "营收同比下降超过20%（{value:.1f}%）",
    },
    {
        "metric": "profit_growth_yoy",
        "condition": "less_than",
        "threshold": -30,
        "type": "financial",
        "severity": "high",
        "template": "净利润同比下降超过30%（{value:.1f}%）",
    },
    {
        "metric": "revenue_growth_yoy",
        "condition": "greater_than",
        "threshold": 50,
        "type": "financial",
        "severity": "medium",
        "template": "营收同比增长超过50%（{value:.1f}%），关注增长质量",
    },
    {
        "metric": "debt_ratio",
        "condition": "greater_than",
        "threshold": 80,
        "type": "financial",
        "severity": "medium",
        "template": "资产负债率超过80%（{value:.1f}%），关注偿债能力",
    },
]


class AlertMonitor:
    """异动监控引擎"""

    @staticmethod
    def scan_watchlist_alerts(db: Session, user_id: str = "default") -> list[dict]:
        """扫描自选股的异动（全量扫描，用于定时任务或手动触发）"""
        # 获取用户自选股
        watchlist_items = (
            db.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .all()
        )

        all_alerts = []
        for item in watchlist_items:
            stock = db.query(Stock).filter(Stock.id == item.stock_id).first()
            if not stock:
                continue

            alerts = AlertMonitor._check_stock_alerts(db, stock, user_id)
            all_alerts.extend(alerts)

        logger.info(f"异动扫描完成: user={user_id}, 发现 {len(all_alerts)} 条异动")
        return all_alerts

    @staticmethod
    def _check_stock_alerts(db: Session, stock: Stock, user_id: str) -> list[dict]:
        """检查单只股票的异动"""
        alerts = []

        # 1. 检查公告异动（最近 7 天）
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_announcements = (
            db.query(Announcement)
            .filter(
                Announcement.stock_id == stock.id,
                Announcement.publish_date >= seven_days_ago.date(),
            )
            .all()
        )

        for ann in recent_announcements:
            matched_rule = AlertMonitor._match_announcement_rule(ann.title)
            if matched_rule:
                # 检查是否已存在相同提醒（避免重复）
                existing = (
                    db.query(StockAlert)
                    .filter(
                        StockAlert.stock_id == stock.id,
                        StockAlert.user_id == user_id,
                        StockAlert.source == ann.title,
                    )
                    .first()
                )
                if not existing:
                    alert = StockAlert(
                        stock_id=stock.id,
                        user_id=user_id,
                        alert_type=matched_rule["type"],
                        severity=matched_rule["severity"],
                        title=f"{stock.name}: {matched_rule['template']}",
                        description=f"公告标题: {ann.title}\n发布日期: {ann.publish_date}",
                        source=ann.title,
                    )
                    db.add(alert)
                    alerts.append({
                        "stock_code": stock.code,
                        "stock_name": stock.name,
                        "alert_type": matched_rule["type"],
                        "severity": matched_rule["severity"],
                        "title": alert.title,
                        "description": alert.description,
                    })

        # 2. 检查财务异动（最新一期 vs 同期）
        fin_alerts = AlertMonitor._check_financial_alerts(db, stock, user_id)
        alerts.extend(fin_alerts)

        if alerts:
            db.commit()

        return alerts

    @staticmethod
    def _match_announcement_rule(title: str) -> Optional[dict]:
        """匹配公告规则"""
        for rule in ANNOUNCEMENT_RULES:
            for keyword in rule["keywords"]:
                if keyword in title:
                    return rule
        return None

    @staticmethod
    def _check_financial_alerts(db: Session, stock: Stock, user_id: str) -> list[dict]:
        """检查财务数据异动"""
        from app.services.data_fetcher import DataFetcher

        alerts = []
        financials = DataFetcher.get_financials(db, stock, fetch_if_missing=False)
        if not financials or len(financials) < 2:
            return alerts

        latest = financials[-1]

        # 银行行业跳过资产负债率检查
        is_bank = stock.industry and "银行" in stock.industry

        for rule in FINANCIAL_RULES:
            if is_bank and rule["metric"] == "debt_ratio":
                continue

            value = latest.get(rule["metric"])
            if value is None:
                continue

            triggered = False
            if rule["condition"] == "greater_than" and value > rule["threshold"]:
                triggered = True
            elif rule["condition"] == "less_than" and value < rule["threshold"]:
                triggered = True

            if triggered:
                alert_title = f"{stock.name}: {rule['template'].format(value=value)}"
                # 检查是否已存在
                existing = (
                    db.query(StockAlert)
                    .filter(
                        StockAlert.stock_id == stock.id,
                        StockAlert.user_id == user_id,
                        StockAlert.title == alert_title,
                        StockAlert.detected_at >= datetime.now() - timedelta(days=30),
                    )
                    .first()
                )
                if not existing:
                    alert = StockAlert(
                        stock_id=stock.id,
                        user_id=user_id,
                        alert_type=rule["type"],
                        severity=rule["severity"],
                        title=alert_title,
                        description=f"最新报告期: {latest['report_period']}",
                        source=f"financial:{rule['metric']}",
                    )
                    db.add(alert)
                    alerts.append({
                        "stock_code": stock.code,
                        "stock_name": stock.name,
                        "alert_type": rule["type"],
                        "severity": rule["severity"],
                        "title": alert_title,
                        "description": alert.description,
                    })

        return alerts

    @staticmethod
    def get_alerts(
        db: Session,
        user_id: str = "default",
        unread_only: bool = False,
        stock_code: Optional[str] = None,
    ) -> list[StockAlert]:
        """获取用户的异动提醒列表"""
        query = db.query(StockAlert).filter(StockAlert.user_id == user_id)

        if unread_only:
            query = query.filter(StockAlert.is_read == False)

        if stock_code:
            stock = db.query(Stock).filter(Stock.code == stock_code).first()
            if stock:
                query = query.filter(StockAlert.stock_id == stock.id)

        return query.order_by(StockAlert.detected_at.desc()).limit(50).all()

    @staticmethod
    def mark_alert_read(db: Session, alert_id: int, user_id: str = "default") -> bool:
        """标记异动为已读"""
        alert = (
            db.query(StockAlert)
            .filter(StockAlert.id == alert_id, StockAlert.user_id == user_id)
            .first()
        )
        if alert:
            alert.is_read = True
            db.commit()
            return True
        return False

    @staticmethod
    def mark_all_read(db: Session, user_id: str = "default"):
        """标记所有异动为已读"""
        db.query(StockAlert).filter(
            StockAlert.user_id == user_id,
            StockAlert.is_read == False,
        ).update({"is_read": True})
        db.commit()

    @staticmethod
    def get_stock_alert_count(db: Session, stock_id: int, user_id: str = "default") -> int:
        """获取某只股票的未读异动数"""
        return (
            db.query(StockAlert)
            .filter(
                StockAlert.stock_id == stock_id,
                StockAlert.user_id == user_id,
                StockAlert.is_read == False,
            )
            .count()
        )

    @staticmethod
    def cleanup_old_alerts(db: Session, days_to_keep: int = 30) -> int:
        """清理过期异常记录
        
        Args:
            db: 数据库会话
            days_to_keep: 保留天数
            
        Returns:
            删除的记录数
        """
        from datetime import datetime
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # 删除过期记录
        result = db.query(StockAlert).filter(
            StockAlert.detected_at < cutoff_date
        ).delete()
        
        db.commit()
        return result