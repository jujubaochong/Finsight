"""
规则化洞察引擎 — 不依赖任何外部 AI / API Key

基于已经计算好的真实财务指标（来自 DataFetcher.get_financials），用确定性的
财务分析规则生成"一句话总结 + 亮点 + 风险 + 指标解读"。

设计目标：
1. 即使 DeepSeek 等 AI 不可用，详情页也能给出**真实、有依据、可读**的分析，
   而不是"AI 分析暂时不可用"这种无用占位。
2. 所有结论都从真实数据推导，并在文字里引用具体数字，杜绝编造。
3. 输出结构与 AI 分析完全一致（summary / strengths / risks / metrics_commentary），
   前端无需区分来源。

它既可作为 AI 不可用时的兜底，也可作为 AI 分析的"事实底座"。
"""
from __future__ import annotations

from typing import Optional


def _fmt(v: Optional[float], unit: str = "", pct: bool = False) -> str:
    """安全格式化数字"""
    if v is None:
        return "—"
    if pct:
        return f"{v:.2f}%"
    return f"{v:.2f}{unit}"


def _period_cn(period: str) -> str:
    """2026Q1 -> 2026年一季报"""
    q_map = {"Q1": "一季报", "Q2": "半年报", "Q3": "三季报", "Q4": "年报"}
    if len(period) >= 6:
        year, q = period[:4], period[4:]
        return f"{year}年{q_map.get(q, q)}"
    return period


class InsightEngine:
    """基于财务指标的规则化分析"""

    @staticmethod
    def analyze(
        stock_info: dict,
        financials: list[dict],
        announcements: list[dict] | None = None,
    ) -> dict:
        """生成与 AI 分析结构一致的洞察结果。

        Returns dict: {summary, strengths, risks, metrics_commentary,
                       highlights(指标卡), source}
        """
        announcements = announcements or []
        name = stock_info.get("name", "该公司")
        industry = stock_info.get("industry") or ""

        if not financials:
            return {
                "summary": f"{name}暂无可用的财务数据，无法生成基本面分析。",
                "strengths": [],
                "risks": ["缺少财务数据，建议点击「刷新数据」重新获取。"],
                "metrics_commentary": "暂无足够数据进行解读。",
                "source": "rule_engine",
            }

        latest = financials[-1]
        period = latest.get("report_period", "")
        period_cn = _period_cn(period)
        is_bank = "银行" in industry

        strengths: list[str] = []
        risks: list[str] = []

        # ---------- 1. 成长性（营收/利润同比） ----------
        rev_g = latest.get("revenue_growth_yoy")
        profit_g = latest.get("profit_growth_yoy")

        if rev_g is not None:
            if rev_g >= 20:
                strengths.append(f"营收高增长：{period_cn}营收同比增长 {rev_g:.1f}%，增长强劲。")
            elif rev_g >= 8:
                strengths.append(f"营收稳健增长：{period_cn}营收同比增长 {rev_g:.1f}%。")
            elif rev_g < 0:
                risks.append(f"营收下滑：{period_cn}营收同比下降 {abs(rev_g):.1f}%，需关注需求或竞争变化。")

        if profit_g is not None:
            if profit_g >= 25:
                strengths.append(f"利润高增长：{period_cn}净利润同比增长 {profit_g:.1f}%。")
            elif profit_g < -15:
                risks.append(f"利润大幅下滑：{period_cn}净利润同比下降 {abs(profit_g):.1f}%，盈利承压。")

        # 增收不增利 / 增利不增收（结构性信号）
        if rev_g is not None and profit_g is not None:
            if rev_g > 5 and profit_g < -5:
                risks.append(
                    f"增收不增利：营收同比 +{rev_g:.1f}% 但净利润同比 {profit_g:.1f}%，"
                    f"可能是成本上升或费用扩张，盈利质量下降。"
                )
            elif rev_g < 0 and profit_g > 15:
                risks.append(
                    f"增利不增收：净利润同比 +{profit_g:.1f}% 但营收同比 {rev_g:.1f}%，"
                    f"利润增长或来自非经常性因素，持续性存疑。"
                )

        # ---------- 2. 盈利能力（净利率 / ROE） ----------
        net_margin = latest.get("net_margin")
        roe = latest.get("roe")

        if net_margin is not None and not is_bank:
            if net_margin >= 25:
                strengths.append(f"高盈利能力：净利率 {net_margin:.1f}%，盈利能力突出。")
            elif net_margin < 3:
                risks.append(f"盈利能力偏弱：净利率仅 {net_margin:.1f}%，利润空间薄。")

        if roe is not None:
            # ROE 注意：季度数据未年化，这里用趋势比较而非绝对阈值更稳妥
            roe_trend = InsightEngine._same_period_metric(financials, period, "roe")
            if roe_trend is not None and roe - roe_trend >= 1:
                strengths.append(
                    f"ROE 改善：{period_cn} ROE {roe:.1f}%，较去年同期（{roe_trend:.1f}%）提升。"
                )
            elif roe_trend is not None and roe_trend - roe >= 2:
                risks.append(
                    f"ROE 下滑：{period_cn} ROE {roe:.1f}%，较去年同期（{roe_trend:.1f}%）下降，"
                    f"股东回报能力走弱。"
                )

        # ---------- 3. 现金流质量（经营现金流 vs 净利润） ----------
        ocf = latest.get("operating_cash_flow")
        net_profit = latest.get("net_profit")
        if ocf is not None and net_profit is not None and net_profit > 0:
            ratio = ocf / net_profit
            if ratio >= 1.0:
                strengths.append(
                    f"利润含金量高：经营现金流（{ocf:.1f}亿）≥ 净利润（{net_profit:.1f}亿），"
                    f"盈利有真实现金支撑。"
                )
            elif ratio < 0.3:
                risks.append(
                    f"利润含金量低：经营现金流（{ocf:.1f}亿）仅为净利润（{net_profit:.1f}亿）的 "
                    f"{ratio*100:.0f}%，存在'纸面利润'风险，需核实应收账款与存货。"
                )
            elif ocf < 0:
                risks.append(
                    f"经营现金流为负（{ocf:.1f}亿）：主营业务'失血'，需高度警惕。"
                )

        # ---------- 4. 杠杆 / 偿债（非银行） ----------
        debt_ratio = latest.get("debt_ratio")
        if debt_ratio is not None and not is_bank:
            if debt_ratio >= 70:
                risks.append(f"高杠杆：资产负债率 {debt_ratio:.1f}%，偿债压力较大，关注利息负担。")
            elif debt_ratio <= 40:
                strengths.append(f"财务稳健：资产负债率仅 {debt_ratio:.1f}%，负债压力小。")

        # ---------- 5. 应收账款 / 存货异常（盈利质量红旗） ----------
        recv = latest.get("receivables")
        if recv is not None and rev_g is not None:
            recv_g = InsightEngine._yoy(financials, period, "receivables")
            if recv_g is not None and recv_g - rev_g > 15:
                risks.append(
                    f"应收账款增速（{recv_g:.1f}%）显著快于营收增速（{rev_g:.1f}%），"
                    f"回款质量可能恶化。"
                )

        # ---------- 6. 公告红旗信号扫描（基于标题关键词） ----------
        ann_risk = InsightEngine._scan_announcements(announcements)
        risks.extend(ann_risk)

        # ---------- 兜底：保证至少各有一条可读结论 ----------
        if not strengths:
            if net_margin is not None and not is_bank:
                strengths.append(f"{period_cn}净利率 {net_margin:.1f}%，盈利能力处于行业一般水平。")
            elif rev_g is not None:
                strengths.append(f"{period_cn}营收同比 {rev_g:+.1f}%，经营总体平稳。")
            else:
                strengths.append(f"已获取 {name} 最新财务数据，可查看下方图表了解趋势。")

        if not risks:
            risks.append("基于现有财务数据，未发现明显的财务风险信号（不构成投资建议）。")

        # ---------- 一句话总结 ----------
        summary = InsightEngine._build_summary(name, period_cn, rev_g, profit_g, net_margin, debt_ratio, is_bank)

        # ---------- 指标解读 ----------
        commentary = InsightEngine._build_commentary(latest, financials, period_cn, is_bank)

        return {
            "summary": summary,
            "strengths": strengths[:4],
            "risks": risks[:4],
            "metrics_commentary": commentary,
            "source": "rule_engine",
        }

    # ---------- helpers ----------

    @staticmethod
    def _yoy(financials: list[dict], period: str, key: str) -> Optional[float]:
        """计算某指标的同比增速（%）"""
        prev = InsightEngine._same_period_metric(financials, period, key)
        cur = next((f.get(key) for f in financials if f.get("report_period") == period), None)
        if prev is None or cur is None or prev == 0:
            return None
        return (cur - prev) / abs(prev) * 100

    @staticmethod
    def _same_period_metric(financials: list[dict], period: str, key: str) -> Optional[float]:
        """取去年同期的某指标值"""
        try:
            year = int(period[:4])
            q = period[4:]
            target = f"{year - 1}{q}"
            for f in financials:
                if f.get("report_period") == target:
                    return f.get(key)
        except (ValueError, IndexError):
            pass
        return None

    @staticmethod
    def _scan_announcements(announcements: list[dict]) -> list[str]:
        """扫描公告标题中的风险关键词"""
        risk_keywords = {
            "减持": "股东减持",
            "问询函": "收到监管问询函",
            "关注函": "收到交易所关注函",
            "立案": "涉及立案调查",
            "处罚": "涉及行政处罚",
            "诉讼": "涉及重大诉讼",
            "质押": "存在股权质押",
            "业绩预减": "业绩预减",
            "业绩预亏": "业绩预亏",
            "辞职": "董监高辞职",
        }
        found = []
        seen = set()
        for a in announcements[:15]:
            title = a.get("title", "")
            for kw, desc in risk_keywords.items():
                if kw in title and desc not in seen:
                    found.append(f"近期公告提示：{desc}（《{title[:30]}》），建议关注。")
                    seen.add(desc)
                    break
        return found[:2]

    @staticmethod
    def _build_summary(name, period_cn, rev_g, profit_g, net_margin, debt_ratio, is_bank) -> str:
        parts = [f"{name}{period_cn}"]
        if rev_g is not None and profit_g is not None:
            rev_word = "增长" if rev_g >= 0 else "下滑"
            profit_word = "增长" if profit_g >= 0 else "下滑"
            parts.append(f"营收同比{rev_word} {abs(rev_g):.1f}%、净利润同比{profit_word} {abs(profit_g):.1f}%")
        elif rev_g is not None:
            parts.append(f"营收同比{'增长' if rev_g>=0 else '下滑'} {abs(rev_g):.1f}%")

        tail = []
        if net_margin is not None and not is_bank:
            tail.append(f"净利率 {net_margin:.1f}%")
        if debt_ratio is not None and not is_bank:
            tail.append(f"资产负债率 {debt_ratio:.1f}%")
        s = "，".join(parts)
        if tail:
            s += "；" + "、".join(tail) + "。"
        else:
            s += "。"
        return s

    @staticmethod
    def _build_commentary(latest, financials, period_cn, is_bank) -> str:
        bits = []
        rev = latest.get("revenue")
        np_ = latest.get("net_profit")
        if rev is not None and np_ is not None:
            bits.append(f"{period_cn}营业收入 {rev:.1f} 亿元、净利润 {np_:.1f} 亿元")
        roe = latest.get("roe")
        if roe is not None:
            bits.append(f"ROE {roe:.1f}%")
        eps = latest.get("eps")
        if eps is not None:
            bits.append(f"每股收益 {eps:.2f} 元")
        if not bits:
            return "可结合下方财务趋势图表综合判断。"
        return "；".join(bits) + "。具体趋势可参考下方图表。"

    @staticmethod
    def build_report_markdown(
        stock_info: dict,
        financials: list[dict],
        announcements: list[dict] | None = None,
    ) -> str:
        """生成规则化的 Markdown 研究报告（AI 不可用时的兜底，全部基于真实数据）。"""
        announcements = announcements or []
        name = stock_info.get("name", "")
        code = stock_info.get("code", "")
        industry = stock_info.get("industry") or "—"
        result = InsightEngine.analyze(stock_info, financials, announcements)

        lines = [f"# {name}（{code}）基本面速览报告", ""]
        lines.append(f"> 所属行业：{industry}　|　数据来源：公开财务报告与公告")
        lines.append("")
        lines.append(f"## 一、核心结论")
        lines.append("")
        lines.append(result["summary"])
        lines.append("")

        # 财务趋势表
        if financials:
            lines.append("## 二、财务数据（近 8 期）")
            lines.append("")
            lines.append("| 报告期 | 营收(亿) | 净利润(亿) | 净利率 | ROE | 资产负债率 | 营收同比 | 净利同比 |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for f in financials[-8:]:
                lines.append(
                    f"| {f.get('report_period','—')} "
                    f"| {_fmt(f.get('revenue'))} "
                    f"| {_fmt(f.get('net_profit'))} "
                    f"| {_fmt(f.get('net_margin'), pct=True)} "
                    f"| {_fmt(f.get('roe'), pct=True)} "
                    f"| {_fmt(f.get('debt_ratio'), pct=True)} "
                    f"| {_fmt(f.get('revenue_growth_yoy'), pct=True)} "
                    f"| {_fmt(f.get('profit_growth_yoy'), pct=True)} |"
                )
            lines.append("")

        lines.append("## 三、亮点")
        lines.append("")
        for s in result["strengths"]:
            lines.append(f"- {s}")
        lines.append("")

        lines.append("## 四、风险提示")
        lines.append("")
        for r in result["risks"]:
            lines.append(f"- {r}")
        lines.append("")

        # 近期公告
        if announcements:
            lines.append("## 五、近期公告")
            lines.append("")
            for a in announcements[:8]:
                title = a.get("title", "")
                date = a.get("date") or a.get("publish_date") or ""
                lines.append(f"- {date} {title}".rstrip())
            lines.append("")

        lines.append("## 六、指标解读")
        lines.append("")
        lines.append(result["metrics_commentary"])
        lines.append("")
        lines.append("---")
        lines.append(
            "**免责声明**：本报告由系统基于公开财务数据自动生成，仅供参考，"
            "不构成任何投资建议。"
        )
        return "\n".join(lines)
