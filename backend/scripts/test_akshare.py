"""
快速自检 AkShare 数据接口可用性

运行：python scripts/test_akshare.py
覆盖 data_fetcher 实际依赖的接口：
  - stock_info_a_code_name   股票列表（搜索）
  - stock_financial_abstract 财务摘要（财务数据主数据源）
  - stock_notice_report      公告（按日期 + 公告类型查询全市场）
"""
import sys

sys.path.append(".")
import time
from datetime import date, timedelta

import akshare as ak


def _last_weekday() -> str:
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def check(label, fn):
    try:
        time.sleep(0.6)
        df = fn()
        if df is None:
            print(f"  [FAIL] {label}: 返回 None")
        elif df.empty:
            print(f"  [WARN] {label}: 数据为空 shape={df.shape}")
        else:
            print(f"  [ OK ] {label}: shape={df.shape} columns={list(df.columns)[:8]}")
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] {label}: {e}")


if __name__ == "__main__":
    print("=== AkShare 接口自检 ===")
    check("股票列表 stock_info_a_code_name", ak.stock_info_a_code_name)
    check(
        "财务摘要 stock_financial_abstract(600519)",
        lambda: ak.stock_financial_abstract(symbol="600519"),
    )
    check(
        "财务摘要 stock_financial_abstract(000001)",
        lambda: ak.stock_financial_abstract(symbol="000001"),
    )
    check(
        f"公告 stock_notice_report(全部, {_last_weekday()})",
        lambda: ak.stock_notice_report(symbol="全部", date=_last_weekday()),
    )
