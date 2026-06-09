"""数据获取层纯函数单元测试（不依赖网络/数据库）"""
import math

import pytest

from app.services.data_fetcher import DataFetcher, _retry_akshare, _to_float, _to_yi


class TestToFloat:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (123, 123.0),
            (1.5, 1.5),
            ("1,234.56", 1234.56),
            ("  42 ", 42.0),
            (None, None),
            ("", None),
            ("--", None),
            ("None", None),
            ("nan", None),
            ("abc", None),
            (float("nan"), None),
            (float("inf"), None),
        ],
    )
    def test_to_float(self, value, expected):
        assert _to_float(value) == expected

    def test_to_yi_converts_to_hundred_million(self):
        assert _to_yi(5_470_291_238_523) == 54702.9124

    def test_to_yi_none(self):
        assert _to_yi(None) is None
        assert _to_yi("--") is None


class TestGuessMarket:
    @pytest.mark.parametrize(
        "code,market",
        [
            ("600519", "SH"),
            ("688981", "SH"),
            ("000001", "SZ"),
            ("300750", "SZ"),
            ("830799", "BJ"),
            ("430139", "BJ"),
        ],
    )
    def test_guess_market(self, code, market):
        assert DataFetcher._guess_market(code) == market


class TestDateToPeriod:
    @pytest.mark.parametrize(
        "date_str,period",
        [
            ("2025-03-31", "2025Q1"),
            ("2025-06-30", "2025Q2"),
            ("2025-09-30", "2025Q3"),
            ("2024-12-31", "2024Q4"),
        ],
    )
    def test_date_to_period(self, date_str, period):
        assert DataFetcher._date_to_period(date_str) == period

    def test_date_to_period_invalid(self):
        assert DataFetcher._date_to_period("garbage") is None


class TestParseDate:
    @pytest.mark.parametrize(
        "text",
        ["2025-03-31", "2025/03/31", "20250331", "2025-03-31 16:00:00"],
    )
    def test_parse_date_formats(self, text):
        d = DataFetcher._parse_date(text)
        assert d is not None
        assert d.year == 2025 and d.month == 3 and d.day == 31

    def test_parse_date_empty(self):
        assert DataFetcher._parse_date("") is None
        assert DataFetcher._parse_date("not-a-date") is None


class TestFindSamePeriodLastYear:
    def test_finds_match(self):
        results = [
            {"report_period": "2024Q1", "revenue": 100},
            {"report_period": "2024Q2", "revenue": 200},
        ]
        match = DataFetcher._find_same_period_last_year(results, "2025Q1")
        assert match is not None and match["revenue"] == 100

    def test_no_match(self):
        results = [{"report_period": "2024Q2", "revenue": 200}]
        assert DataFetcher._find_same_period_last_year(results, "2025Q1") is None


class TestRetryAkshare:
    def test_returns_value_on_success(self):
        assert _retry_akshare(lambda: 42) == 42

    def test_retries_then_succeeds(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("boom")
            return "ok"

        assert _retry_akshare(flaky, retries=3) == "ok"
        assert calls["n"] == 3

    def test_raises_last_exception(self):
        def always_fail():
            raise ValueError("nope")

        with pytest.raises(ValueError, match="nope"):
            _retry_akshare(always_fail, retries=2)
