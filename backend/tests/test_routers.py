"""股票路由单元测试

重点验证「刷新接口不再在请求路径上做重活」这一与超时修复直接相关的行为：
  - 财务数据同步刷新（定向查询，受单次调用超时兜底）；
  - 公告改为后台异步刷新（全市场抓取很重，时间预算 ~130s 远超前端 60s 超时，
    若同步执行刷新接口会卡死/超时）。
"""
import pytest
from fastapi import HTTPException

from app.routers import stocks as stocks_router
from app.services.data_fetcher import DataFetcher


class TestRefreshEndpoint:
    def test_refresh_syncs_financials_and_backgrounds_announcements(
        self, db, sample_stock, monkeypatch
    ):
        calls = {"fin_sync": 0, "ann_async": 0, "ann_sync": 0}

        monkeypatch.setattr(
            DataFetcher,
            "_sync_financials",
            lambda d, s: calls.__setitem__("fin_sync", calls["fin_sync"] + 1),
        )
        monkeypatch.setattr(
            DataFetcher,
            "_trigger_announcements_sync_async",
            lambda code: calls.__setitem__("ann_async", calls["ann_async"] + 1),
        )
        # 公告绝不能在请求路径上被【同步】抓取（那是导致刷新超时的重活）
        monkeypatch.setattr(
            DataFetcher,
            "_sync_announcements",
            lambda d, s: calls.__setitem__("ann_sync", calls["ann_sync"] + 1),
        )

        result = stocks_router.refresh_stock_data(sample_stock.code, db)

        assert result["success"] is True
        assert calls["fin_sync"] == 1   # 财务：同步刷新
        assert calls["ann_async"] == 1  # 公告：触发后台异步刷新
        assert calls["ann_sync"] == 0   # 公告：绝不在请求路径上同步抓取

    def test_refresh_unknown_code_returns_404(self, db):
        with pytest.raises(HTTPException) as exc_info:
            stocks_router.refresh_stock_data("999999", db)
        assert exc_info.value.status_code == 404

    def test_refresh_invalidates_caches(self, db, sample_stock, monkeypatch):
        from app.cache import cache

        # 预置缓存，模拟此前已同步过的状态
        cache.set(f"fin_synced:{sample_stock.code}", True, 600)
        cache.set(f"ann_synced:{sample_stock.code}", True, 600)
        cache.set("notice_pool", {"600519": []}, 600)

        monkeypatch.setattr(DataFetcher, "_sync_financials", lambda d, s: None)
        monkeypatch.setattr(
            DataFetcher, "_trigger_announcements_sync_async", lambda code: None
        )

        stocks_router.refresh_stock_data(sample_stock.code, db)

        # 刷新应失效相关缓存，确保下次拉取最新数据
        assert cache.get(f"fin_synced:{sample_stock.code}") is None
        assert cache.get(f"ann_synced:{sample_stock.code}") is None
        assert cache.get("notice_pool") is None


class TestSearchEndpoint:
    def test_search_returns_response_shape(self, db, sample_stock):
        resp = stocks_router.search_stocks("茅台", db)
        assert resp.query == "茅台"
        assert resp.total == 1
        assert resp.results[0].code == "600519"
