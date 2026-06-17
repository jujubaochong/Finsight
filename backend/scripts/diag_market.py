"""
行情数据诊断脚本 —— 按与后端完全一致的顺序加载网络补丁后，逐项测试。

用法（在 backend 目录下）：
    python -m scripts.diag_market
或：
    python scripts/diag_market.py

它会依次检查：禁用代理 + 强制IPv4 -> K线(东财/新浪) -> 资金流 -> 完整快照。
任何一步失败都会打印明确原因，便于定位是"网络""数据源"还是"代码"问题。
"""
import sys
import os

# 确保能 import app.*（无论从哪个目录运行）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 关键：与 main.py 完全一致的顺序——先打补丁，再 import 任何 akshare 相关模块
from app.net_setup import disable_system_proxy, force_ipv4
disable_system_proxy()
force_ipv4()

import socket
print("=" * 50)
print("[1] 网络补丁检查")
try:
    fams = {r[0] for r in socket.getaddrinfo("www.baidu.com", 443)}
    print("    getaddrinfo 返回地址族:", fams, "(应仅含 AF_INET=IPv4)")
except Exception as e:
    print("    解析失败:", e)

import requests
s = requests.Session()
print("    requests Session trust_env:", s.trust_env, "proxies:", s.proxies)

print("=" * 50)
print("[2] K线（含东财->新浪兜底）")
from app.services.market_data import fetch_kline, fetch_fundflow, get_market_snapshot
kline = fetch_kline("000725")
print(f"    K线条数: {len(kline)}")
if kline:
    print("    最新一条:", kline[-1])

print("=" * 50)
print("[3] 资金流")
ff = fetch_fundflow("000725")
print(f"    资金流条数: {len(ff)}")
if ff:
    print("    最新一条:", ff[-1])

print("=" * 50)
print("[4] 完整快照（技术面板/AI短线研判依赖它）")
snap = get_market_snapshot("000725", include_lhb=False)
ind = snap.get("indicators", {})
fund = snap.get("fund_flow", {})
print("    latest:", snap.get("latest"))
print("    indicators 是否有数据:", bool(ind), "| MA5:", ind.get("ma5"), "MACD:", ind.get("macd"))
print("    fund_flow 是否有数据:", bool(fund), "| 信号:", fund.get("label"))
print("    main_phase:", snap.get("main_phase", {}).get("label"))

print("=" * 50)
if ind or fund:
    print("结论: ✅ 后端能拿到数据。若前端仍空，请重启后端 + 确认前端代理端口与后端一致。")
else:
    print("结论: ❌ 后端拿不到数据。请把上面 [2][3] 的报错或 0 条信息发给我。")
