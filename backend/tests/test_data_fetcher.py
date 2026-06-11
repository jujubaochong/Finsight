"""DataFetcher 数据库交互 + akshare 解析单元测试（mock 网络）"""
import pandas as pd
import pytest

import app.services.data_fetcher as df_module
from app.models.stock import Announcement, Financial, Stock
from app.services.data_fetcher import DataFetcher


# ---------- 财务摘要解析 ----------

def _make_abstract_df():
    """构造一个与 ak.stock_financial_abstract 结构一致的 DataFrame
    （列=报告期，行=指标；金额单位为元）
    """
    rows = [
        ("常用指标", "营业总收入", 100e8, 80e8),
        ("常用指标", "净利润", 50e8, 40e8),
        ("常用指标", "股东权益合计(净资产)", 200e8, 180e8),
        ("常用指标", "经营现金流量净额", 60e8, 55e8),
        ("常用指标", "基本每股收益", 4.0, 3.2),
        ("常用指标", "商誉", float("nan"), float("nan")),
        ("财务风险", "资产负债率", 20.0, 25.0),
    ]
    return pd.DataFrame(rows, columns=["选项", "指标", "20250331", "20240331"])


class TestParseAbstractFinancials:
    def test_parses_periods_and_units(self, db, sample_stock):
        count = DataFetcher._parse_abstract_financials(db, sample_stock, _make_abstract_df())
        assert count == 2

        fins = {f.report_period: f for f in db.query(Financial).all()}
        assert set(fins) == {"2025Q1", "2024Q1"}

        q1 = fins["2025Q1"]
        # 元 → 亿元
        assert q1.revenue == 100.0
        assert q1.net_profit == 50.0
        assert q1.total_equity == 200.0
        assert q1.operating_cash_flow == 60.0
        assert q1.eps == 4.0
        assert q1.goodwill is None  # NaN -> None
        # 由净资产 + 资产负债率(20%) 推导总资产/总负债
        assert q1.total_assets == pytest.approx(250.0, rel=1e-4)
        assert q1.total_liability == pytest.approx(50.0, rel=1e-4)

    def test_skips_existing_periods(self, db, sample_stock):
        DataFetcher._parse_abstract_financials(db, sample_stock, _make_abstract_df())
        # 再次解析相同数据不应重复插入
        count = DataFetcher._parse_abstract_financials(db, sample_stock, _make_abstract_df())
        assert count == 0
        assert db.query(Financial).count() == 2

    def test_missing_indicator_column_returns_zero(self, db, sample_stock):
        bad = pd.DataFrame({"foo": [1], "20250331": [2]})
        assert DataFetcher._parse_abstract_financials(db, sample_stock, bad) == 0

    def test_no_date_columns_returns_zero(self, db, sample_stock):
        bad = pd.DataFrame({"选项": ["x"], "指标": ["营业总收入"], "备注": [1]})
        assert DataFetcher._parse_abstract_financials(db, sample_stock, bad) == 0


# ---------- 计算指标 ----------

class TestGetFinancials:
    def test_computed_metrics(self, db, sample_stock):
        DataFetcher._parse_abstract_financials(db, sample_stock, _make_abstract_df())
        db.refresh(sample_stock)
        results = DataFetcher.get_financials(db, sample_stock)

        assert [r["report_period"] for r in results] == ["2024Q1", "2025Q1"]
        q1 = results[-1]
        assert q1["net_margin"] == pytest.approx(50.0)   # 50/100
        assert q1["roe"] == pytest.approx(25.0)           # 50/200
        assert q1["debt_ratio"] == pytest.approx(20.0)    # 50/250
        assert q1["revenue_growth_yoy"] == pytest.approx(25.0)  # (100-80)/80
        assert q1["profit_growth_yoy"] == pytest.approx(25.0)   # (50-40)/40


# ---------- 财务同步：成功 & 降级 ----------

class TestSyncFinancials:
    def test_uses_real_data(self, db, sample_stock, monkeypatch):
        monkeypatch.setattr(
            df_module.ak, "stock_financial_abstract",
            lambda symbol: _make_abstract_df(),
        )
        DataFetcher._sync_financials(db, sample_stock)
        assert db.query(Financial).count() == 2

    def test_falls_back_to_mock_when_api_fails(self, db, sample_stock, monkeypatch):
        def boom(symbol):
            raise ConnectionError("network down")

        monkeypatch.setattr(df_module.ak, "stock_financial_abstract", boom)
        DataFetcher._sync_financials(db, sample_stock)
        # 降级方案应生成模拟数据
        assert db.query(Financial).count() > 0

    def test_falls_back_when_empty(self, db, sample_stock, monkeypatch):
        monkeypatch.setattr(
            df_module.ak, "stock_financial_abstract",
            lambda symbol: pd.DataFrame(),
        )
        DataFetcher._sync_financials(db, sample_stock)
        assert db.query(Financial).count() > 0


# ---------- 行业同步 ----------

class TestSyncIndustries:
    def test_maps_industry_from_sw(self, db, monkeypatch):
        db.add(Stock(code="600519", name="贵州茅台", market="SH"))
        db.add(Stock(code="000001", name="平安银行", market="SZ"))
        db.commit()

        def fake_first_info():
            return pd.DataFrame(
                {"行业代码": ["801120.SI", "801780.SI"], "行业名称": ["食品饮料", "银行"]}
            )

        def fake_cons(symbol):
            mapping = {
                "801120": ["600519"],
                "801780": ["000001"],
            }
            return pd.DataFrame({"证券代码": mapping.get(symbol, [])})

        monkeypatch.setattr(df_module.ak, "sw_index_first_info", fake_first_info)
        monkeypatch.setattr(df_module.ak, "index_component_sw", fake_cons)

        updated = DataFetcher._sync_industries(db, force=True)
        assert updated == 2
        assert db.query(Stock).filter(Stock.code == "600519").first().industry == "食品饮料"
        assert db.query(Stock).filter(Stock.code == "000001").first().industry == "银行"

    def test_skips_when_cached(self, db, monkeypatch):
        from app.cache import cache

        cache.set("industries_synced", True, 60)
        called = {"n": 0}

        def fake_first_info():
            called["n"] += 1
            return pd.DataFrame()

        monkeypatch.setattr(df_module.ak, "sw_index_first_info", fake_first_info)
        assert DataFetcher._sync_industries(db, force=False) == 0
        assert called["n"] == 0  # 命中缓存，未调用接口


# ---------- 公告 ----------

def _make_notice_df():
    return pd.DataFrame(
        {
            "代码": ["600519", "000001"],
            "名称": ["贵州茅台", "平安银行"],
            "公告标题": ["茅台:2025年第一季度报告", "平安:股东大会决议"],
            "公告类型": ["财报", "其他"],
            "公告日期": ["2025-04-01", "2025-04-01"],
            "网址": ["http://x/1", "http://x/2"],
        }
    )


class TestAnnouncements:
    def test_fetch_pool_and_save(self, db, sample_stock, monkeypatch):
        monkeypatch.setattr(
            df_module.ak, "stock_notice_report",
            lambda symbol, date: _make_notice_df(),
        )
        DataFetcher._sync_announcements(db, sample_stock)
        anns = db.query(Announcement).filter(
            Announcement.stock_id == sample_stock.id
        ).all()
        assert len(anns) == 1
        assert anns[0].title.startswith("茅台")

    def test_fallback_when_no_notices(self, db, sample_stock, monkeypatch):
        monkeypatch.setattr(
            df_module.ak, "stock_notice_report",
            lambda symbol, date: pd.DataFrame(),
        )
        DataFetcher._sync_announcements(db, sample_stock)
        # 无真实公告 → 模拟公告兜底
        assert db.query(Announcement).count() > 0


# ---------- 搜索 ----------

class TestSearch:
    def test_search_db_hit_no_network(self, db, sample_stock, monkeypatch):
        def boom():
            raise AssertionError("不应触发网络同步")

        monkeypatch.setattr(df_module.ak, "stock_info_a_code_name", boom)
        results = DataFetcher.search_stock(db, "茅台")
        assert len(results) == 1
        assert results[0]["code"] == "600519"

    def test_search_empty_keyword(self, db):
        assert DataFetcher.search_stock(db, "   ") == []

    def test_search_miss_is_nonblocking_and_triggers_background_sync(
        self, db, monkeypatch
    ):
        """数据库未命中：立即返回空结果（不阻塞网络下载），并触发后台同步。

        这是消除「搜索超时」的关键行为——慢速的全量股票列表下载被移出请求路径，
        改为后台异步执行，因此本次请求绝不会去碰网络。
        """
        calls = {"n": 0}
        monkeypatch.setattr(
            DataFetcher,
            "_trigger_stock_list_sync_async",
            lambda: calls.__setitem__("n", calls["n"] + 1),
        )

        # 若请求路径上意外触发了网络同步，立即失败
        def boom():
            raise AssertionError("搜索请求路径上不应触发网络同步")

        monkeypatch.setattr(df_module.ak, "stock_info_a_code_name", boom)

        results = DataFetcher.search_stock(db, "平安")
        assert results == []          # 未命中立即返回空，不阻塞
        assert calls["n"] == 1        # 但已触发一次后台同步

    def test_sync_stock_list_populates_db(self, db, monkeypatch):
        """后台同步逻辑本身：把 akshare 股票列表写入数据库，后续搜索即可命中。"""
        monkeypatch.setattr(
            df_module.ak,
            "stock_info_a_code_name",
            lambda: pd.DataFrame(
                {"code": ["000001", "600519"], "name": ["平安银行", "贵州茅台"]}
            ),
        )
        DataFetcher._sync_stock_list(db)
        assert db.query(Stock).count() == 2

        hit = DataFetcher._query_stocks(db, "平安")
        assert len(hit) == 1
        assert hit[0]["code"] == "000001"
