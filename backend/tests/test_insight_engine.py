"""规则化洞察引擎单元测试（不依赖网络/AI）"""
from app.services.insight_engine import InsightEngine


def _fin(period, revenue, net_profit, **kw):
    base = {
        "report_period": period,
        "revenue": revenue,
        "net_profit": net_profit,
        "total_equity": None,
        "operating_cash_flow": None,
        "receivables": None,
        "eps": None,
        "net_margin": None,
        "roe": None,
        "debt_ratio": None,
        "revenue_growth_yoy": None,
        "profit_growth_yoy": None,
    }
    base.update(kw)
    return base


class TestInsightEngine:
    def test_empty_financials(self):
        r = InsightEngine.analyze({"name": "测试股"}, [])
        assert "暂无可用的财务数据" in r["summary"]
        assert r["source"] == "rule_engine"

    def test_always_outputs_strengths_and_risks(self):
        fins = [_fin("2026Q1", 100.0, 50.0, net_margin=50.0, debt_ratio=12.0)]
        r = InsightEngine.analyze({"name": "贵州茅台", "industry": "食品饮料"}, fins)
        # 不论数据如何，亮点和风险都不为空（保证页面有内容）
        assert len(r["strengths"]) >= 1
        assert len(r["risks"]) >= 1
        assert "贵州茅台" in r["summary"]

    def test_high_profitability_is_strength(self):
        fins = [_fin("2026Q1", 100.0, 50.0, net_margin=50.0, debt_ratio=12.0)]
        r = InsightEngine.analyze({"name": "X", "industry": "食品饮料"}, fins)
        assert any("盈利能力" in s for s in r["strengths"])

    def test_revenue_decline_is_risk(self):
        fins = [_fin("2026Q1", 80.0, 20.0, revenue_growth_yoy=-15.0)]
        r = InsightEngine.analyze({"name": "X", "industry": "制造"}, fins)
        assert any("营收下滑" in x for x in r["risks"])

    def test_low_cash_flow_quality_flagged(self):
        # 经营现金流远低于净利润 → 纸面利润风险
        fins = [_fin("2026Q1", 100.0, 50.0, operating_cash_flow=5.0)]
        r = InsightEngine.analyze({"name": "X", "industry": "制造"}, fins)
        assert any("含金量低" in x or "纸面利润" in x for x in r["risks"])

    def test_bank_skips_debt_ratio(self):
        # 银行高负债率是正常的，不应作为风险
        fins = [_fin("2026Q1", 100.0, 40.0, debt_ratio=92.0)]
        r = InsightEngine.analyze({"name": "某银行", "industry": "银行"}, fins)
        assert not any("高杠杆" in x for x in r["risks"])

    def test_revenue_up_profit_down_structural_signal(self):
        fins = [_fin("2026Q1", 100.0, 30.0, revenue_growth_yoy=10.0, profit_growth_yoy=-10.0)]
        r = InsightEngine.analyze({"name": "X", "industry": "制造"}, fins)
        assert any("增收不增利" in x for x in r["risks"])

    def test_announcement_risk_scan(self):
        fins = [_fin("2026Q1", 100.0, 50.0, net_margin=50.0)]
        anns = [{"title": "某公司:关于控股股东减持股份的公告"}]
        r = InsightEngine.analyze({"name": "X", "industry": "制造"}, fins, anns)
        assert any("减持" in x for x in r["risks"])

    def test_report_markdown_contains_real_data(self):
        fins = [
            _fin("2025Q1", 90.0, 45.0, net_margin=50.0, roe=9.0),
            _fin("2026Q1", 100.0, 50.0, net_margin=50.0, roe=10.0,
                 revenue_growth_yoy=11.1, profit_growth_yoy=11.1),
        ]
        md = InsightEngine.build_report_markdown(
            {"name": "贵州茅台", "code": "600519", "industry": "食品饮料"}, fins
        )
        assert "贵州茅台" in md
        assert "2026Q1" in md
        assert "免责声明" in md
        assert "## " in md  # 含章节标题
