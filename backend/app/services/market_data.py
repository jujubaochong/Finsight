"""
行情/技术面/资金面服务 — 封装 K线、技术指标、主力资金流、龙虎榜

设计要点（性能优先）：
  1. K线、资金流两个核心接口【并行抓取】（线程池），把串行等待压成单次等待。
  2. 全部结果【带缓存】（盘中 TTL 较短，避免重复抓取）。
  3. 技术指标（MA / MACD / KDJ / RSI）用纯 pandas 计算，无额外网络。
  4. 单次 akshare 调用复用 data_fetcher 的超时机制，杜绝无限阻塞。
  5. 龙虎榜接口较慢（全市场），按需 + 长缓存，绝不放在主路径上同步等待。
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Optional

import akshare as ak

from app.cache import cache
from app.services.data_fetcher import _retry_akshare

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="market")

# 缓存 TTL（秒）
_TTL_KLINE = 1800        # K线 30 分钟
_TTL_FUNDFLOW = 1800     # 资金流 30 分钟
_TTL_LHB = 21600         # 龙虎榜 6 小时
_KLINE_DAYS = 120        # 默认拉取最近 120 个自然日的日线


def _market_of(code: str) -> str:
    return "sh" if code.startswith("6") else ("bj" if code.startswith(("8", "4")) else "sz")


def _safe_float(v) -> Optional[float]:
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


# ============== 原始数据抓取（带缓存） ==============

def fetch_kline(code: str, days: int = _KLINE_DAYS) -> list[dict]:
    """拉取日K线（前复权）。返回 [{date, open, high, low, close, volume, amount, pct_chg, turnover}]"""
    ck = f"kline:{code}:{days}"
    cached = cache.get(ck)
    if cached is not None:
        return cached

    start = (date.today() - timedelta(days=days)).strftime("%Y%m%d")
    df = _retry_akshare(
        ak.stock_zh_a_hist,
        symbol=code,
        period="daily",
        adjust="qfq",
        start_date=start,
        retries=2,
    )
    rows: list[dict] = []
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            rows.append({
                "date": str(r.get("日期", "")),
                "open": _safe_float(r.get("开盘")),
                "high": _safe_float(r.get("最高")),
                "low": _safe_float(r.get("最低")),
                "close": _safe_float(r.get("收盘")),
                "volume": _safe_float(r.get("成交量")),
                "amount": _safe_float(r.get("成交额")),
                "pct_chg": _safe_float(r.get("涨跌幅")),
                "turnover": _safe_float(r.get("换手率")),
            })
    cache.set(ck, rows, _TTL_KLINE)
    return rows


def fetch_fundflow(code: str) -> list[dict]:
    """拉取个股资金流（主力/超大单/大单/中单/小单净额及占比）"""
    ck = f"fundflow:{code}"
    cached = cache.get(ck)
    if cached is not None:
        return cached

    df = _retry_akshare(
        ak.stock_individual_fund_flow,
        stock=code,
        market=_market_of(code),
        retries=2,
    )
    rows: list[dict] = []
    if df is not None and not df.empty:
        for _, r in df.iterrows():
            rows.append({
                "date": str(r.get("日期", "")),
                "close": _safe_float(r.get("收盘价")),
                "pct_chg": _safe_float(r.get("涨跌幅")),
                "main_net": _safe_float(r.get("主力净流入-净额")),
                "main_net_pct": _safe_float(r.get("主力净流入-净占比")),
                "xl_net": _safe_float(r.get("超大单净流入-净额")),
                "l_net": _safe_float(r.get("大单净流入-净额")),
                "m_net": _safe_float(r.get("中单净流入-净额")),
                "s_net": _safe_float(r.get("小单净流入-净额")),
            })
    cache.set(ck, rows, _TTL_FUNDFLOW)
    return rows


# ============== 技术指标计算（纯计算，无网络） ==============

def _ema(values: list[float], span: int) -> list[float]:
    k = 2 / (span + 1)
    out: list[float] = []
    prev = None
    for v in values:
        prev = v if prev is None else (v * k + prev * (1 - k))
        out.append(prev)
    return out


def _sma(values: list[float], n: int) -> list[Optional[float]]:
    out: list[Optional[float]] = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        out.append(round(s / n, 3) if i >= n - 1 else None)
    return out


def compute_indicators(kline: list[dict]) -> dict:
    """基于 K线计算 MA / MACD / KDJ / RSI，返回最新值 + 用于画图的序列"""
    closes = [k["close"] for k in kline if k["close"] is not None]
    if len(closes) < 35:
        return {}

    dates = [k["date"] for k in kline if k["close"] is not None]
    highs = [k["high"] for k in kline if k["close"] is not None]
    lows = [k["low"] for k in kline if k["close"] is not None]

    # MA
    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)

    # MACD (12,26,9)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif = [round(a - b, 4) for a, b in zip(ema12, ema26)]
    dea = _ema(dif, 9)
    macd = [round((d - e) * 2, 4) for d, e in zip(dif, dea)]

    # KDJ (9,3,3)
    k_list, d_list, j_list = [], [], []
    pk, pd_ = 50.0, 50.0
    for i in range(len(closes)):
        lo = min(lows[max(0, i - 8): i + 1])
        hi = max(highs[max(0, i - 8): i + 1])
        rsv = 50.0 if hi == lo else (closes[i] - lo) / (hi - lo) * 100
        pk = 2 / 3 * pk + 1 / 3 * rsv
        pd_ = 2 / 3 * pd_ + 1 / 3 * pk
        k_list.append(round(pk, 2)); d_list.append(round(pd_, 2)); j_list.append(round(3 * pk - 2 * pd_, 2))

    # RSI(14)
    gains, losses = [0.0], [0.0]
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0)); losses.append(max(-ch, 0))
    avg_g = _ema(gains, 14); avg_l = _ema(losses, 14)
    rsi = [round(100 - 100 / (1 + (g / l)), 2) if l > 1e-9 else 100.0 for g, l in zip(avg_g, avg_l)]

    n = len(closes)
    def last(x):
        return x[n - 1] if x and x[n - 1] is not None else None

    # 画图序列只取最近 60 根，控制传输量
    span = slice(max(0, n - 60), n)
    series = [
        {"date": dates[i], "close": closes[i], "dif": dif[i], "dea": dea[i], "macd": macd[i]}
        for i in range(*span.indices(n))
    ]

    # 金叉/死叉判断
    macd_cross = "none"
    if n >= 2:
        if dif[n - 2] <= dea[n - 2] and dif[n - 1] > dea[n - 1]:
            macd_cross = "golden"
        elif dif[n - 2] >= dea[n - 2] and dif[n - 1] < dea[n - 1]:
            macd_cross = "dead"

    return {
        "ma5": last(ma5), "ma10": last(ma10), "ma20": last(ma20), "ma60": last(ma60),
        "macd_dif": last(dif), "macd_dea": last(dea), "macd": last(macd), "macd_cross": macd_cross,
        "kdj_k": last(k_list), "kdj_d": last(d_list), "kdj_j": last(j_list),
        "rsi": last(rsi),
        "series": series,
    }


# ============== 资金面研判 ==============

def analyze_fundflow(fundflow: list[dict]) -> dict:
    """基于近 N 日资金流，给出主力行为信号（吸筹/出货/震荡）"""
    if not fundflow:
        return {}
    recent = fundflow[-5:]
    main_nets = [r["main_net"] for r in recent if r["main_net"] is not None]
    if not main_nets:
        return {}
    total_main = sum(main_nets)
    pos_days = sum(1 for v in main_nets if v > 0)
    last = recent[-1]

    # 信号判断
    if pos_days >= 4 and total_main > 0:
        signal, label = "accumulate", "主力持续净流入（疑似吸筹）"
    elif pos_days <= 1 and total_main < 0:
        signal, label = "distribute", "主力持续净流出（疑似出货）"
    else:
        signal, label = "neutral", "主力资金多空交织（震荡）"

    return {
        "signal": signal,
        "label": label,
        "main_net_5d": round(total_main / 1e8, 2),        # 5日主力净额（亿）
        "main_net_today": round((last["main_net"] or 0) / 1e8, 2),
        "main_net_pct_today": last.get("main_net_pct"),
        "positive_days_5d": pos_days,
        "series": [
            {"date": r["date"], "main_net": round((r["main_net"] or 0) / 1e8, 3),
             "pct_chg": r["pct_chg"]}
            for r in fundflow[-20:]
        ],
    }


# ============== 龙虎榜（慢接口，长缓存，按需） ==============

def fetch_lhb_for(code: str, lookback_days: int = 30) -> list[dict]:
    """获取某只股票近期龙虎榜记录（全市场抓取后过滤；长缓存）"""
    ck = f"lhb_pool:{lookback_days}"
    pool = cache.get(ck)
    if pool is None:
        end = date.today().strftime("%Y%m%d")
        start = (date.today() - timedelta(days=lookback_days)).strftime("%Y%m%d")
        df = _retry_akshare(
            ak.stock_lhb_detail_em, start_date=start, end_date=end, retries=1, timeout=60,
        )
        pool = {}
        if df is not None and not df.empty:
            for _, r in df.iterrows():
                c = str(r.get("代码", "")).strip()
                if not c:
                    continue
                pool.setdefault(c, []).append({
                    "date": str(r.get("上榜日", "")),
                    "reason": str(r.get("上榜原因", "")),
                    "interpret": str(r.get("解读", "")),
                    "net_buy": _safe_float(r.get("龙虎榜净买额")),
                    "pct_chg": _safe_float(r.get("涨跌幅")),
                    "after_1d": _safe_float(r.get("上榜后1日")),
                    "after_5d": _safe_float(r.get("上榜后5日")),
                })
        cache.set(ck, pool, _TTL_LHB)
    return pool.get(code, [])


# ============== 聚合（并行抓取，性能关键） ==============

def get_market_snapshot(code: str, include_lhb: bool = False) -> dict:
    """并行抓取 K线 + 资金流，计算技术/资金信号，一次性返回。

    K线和资金流互不依赖，用线程池并行，把两次网络等待压成一次。
    """
    futures = {
        _executor.submit(fetch_kline, code): "kline",
        _executor.submit(fetch_fundflow, code): "fundflow",
    }
    if include_lhb:
        futures[_executor.submit(fetch_lhb_for, code)] = "lhb"

    results: dict = {}
    for fut in as_completed(futures):
        key = futures[fut]
        try:
            results[key] = fut.result()
        except Exception as e:  # noqa: BLE001
            logger.warning("行情抓取失败 %s/%s: %s", code, key, e)
            results[key] = []

    kline = results.get("kline", [])
    fundflow = results.get("fundflow", [])
    indicators = compute_indicators(kline) if kline else {}
    fund_signal = analyze_fundflow(fundflow) if fundflow else {}

    # 最新价与近5日涨跌
    latest = kline[-1] if kline else {}
    chg_5d = None
    if len(kline) >= 6 and kline[-6]["close"]:
        chg_5d = round((kline[-1]["close"] - kline[-6]["close"]) / kline[-6]["close"] * 100, 2)

    snap = {
        "code": code,
        "latest": {
            "date": latest.get("date"),
            "close": latest.get("close"),
            "pct_chg": latest.get("pct_chg"),
            "turnover": latest.get("turnover"),
            "chg_5d": chg_5d,
        },
        "indicators": indicators,
        "fund_flow": fund_signal,
        "lhb": results.get("lhb", []),
    }
    # 主力阶段研判（规则推断）
    snap["main_phase"] = judge_main_phase(snap)
    return snap



# ============== 市场概览：板块 + 潜力股（首页用） ==============

_TTL_OVERVIEW = 900  # 概览缓存 15 分钟


def fetch_industry_boards(top: int = 8) -> list[dict]:
    """行业板块行情（按涨跌幅排序，取领涨/领跌）"""
    ck = f"ind_boards:{top}"
    cached = cache.get(ck)
    if cached is not None:
        return cached

    df = _retry_akshare(ak.stock_board_industry_name_em, retries=1, timeout=30)
    rows: list[dict] = []
    if df is not None and not df.empty:
        # 兼容列名差异
        def col(*names):
            for n in names:
                if n in df.columns:
                    return n
            return None
        c_name = col("板块名称", "名称")
        c_pct = col("涨跌幅")
        c_lead = col("领涨股票", "领涨股")
        c_price = col("最新价")
        if c_name and c_pct:
            df = df.sort_values(c_pct, ascending=False)
            for _, r in df.head(top).iterrows():
                rows.append({
                    "name": str(r.get(c_name, "")),
                    "pct_chg": _safe_float(r.get(c_pct)),
                    "lead_stock": str(r.get(c_lead, "")) if c_lead else "",
                    "price": _safe_float(r.get(c_price)) if c_price else None,
                })
    cache.set(ck, rows, _TTL_OVERVIEW)
    return rows


def fetch_potential_stocks(top: int = 10) -> list[dict]:
    """潜力股：按当日主力净流入排行 + 适度涨幅过滤（强势但非涨停板）"""
    ck = f"potential:{top}"
    cached = cache.get(ck)
    if cached is not None:
        return cached

    df = _retry_akshare(
        ak.stock_individual_fund_flow_rank, indicator="今日", retries=1, timeout=30
    )
    rows: list[dict] = []
    if df is not None and not df.empty:
        def col(*names):
            for n in names:
                if n in df.columns:
                    return n
            return None
        c_code = col("代码")
        c_name = col("名称")
        c_price = col("最新价")
        c_pct = col("今日涨跌幅", "涨跌幅")
        c_main = col("今日主力净流入-净额", "主力净流入-净额")
        c_main_pct = col("今日主力净流入-净占比", "主力净流入-净占比")
        if c_code and c_main:
            # 主力净流入为正、涨幅在 1%~8%（强势但非追高涨停）
            df = df.copy()
            df["_main"] = df[c_main].apply(_safe_float)
            df["_pct"] = df[c_pct].apply(_safe_float) if c_pct else 0
            df = df[df["_main"].notna() & (df["_main"] > 0)]
            if c_pct:
                df = df[(df["_pct"] >= 1) & (df["_pct"] <= 8)]
            df = df.sort_values("_main", ascending=False)
            for _, r in df.head(top).iterrows():
                code = str(r.get(c_code, "")).strip()
                if len(code) != 6 or not code.isdigit():
                    continue
                rows.append({
                    "code": code,
                    "name": str(r.get(c_name, "")),
                    "price": _safe_float(r.get(c_price)) if c_price else None,
                    "pct_chg": _safe_float(r.get(c_pct)) if c_pct else None,
                    "main_net": round((_safe_float(r.get(c_main)) or 0) / 1e8, 2),
                    "main_net_pct": _safe_float(r.get(c_main_pct)) if c_main_pct else None,
                })
    cache.set(ck, rows, _TTL_OVERVIEW)
    return rows


def get_market_overview() -> dict:
    """首页市场概览：板块 + 潜力股（并行抓取）"""
    f_board = _executor.submit(fetch_industry_boards)
    f_pot = _executor.submit(fetch_potential_stocks)
    boards, potential = [], []
    try:
        boards = f_board.result()
    except Exception as e:  # noqa: BLE001
        logger.warning("板块抓取失败: %s", e)
    try:
        potential = f_pot.result()
    except Exception as e:  # noqa: BLE001
        logger.warning("潜力股抓取失败: %s", e)
    return {"boards": boards, "potential": potential}


# ============== 主力阶段研判（建仓/启动/离场） ==============

def judge_main_phase(snapshot: dict) -> dict:
    """基于资金流 + 量价 + 均线，规则判断主力所处阶段。

    返回 {phase, label, color, reasons[]}，纯规则推断，作为 AI 研判的补充与兜底。
    阶段：building(建仓/吸筹) / launching(启动) / leaving(离场/派发) / unknown(观望)
    """
    ff = snapshot.get("fund_flow", {})
    ind = snapshot.get("indicators", {})
    latest = snapshot.get("latest", {})

    main_5d = ff.get("main_net_5d")
    pos_days = ff.get("positive_days_5d")
    pct_today = latest.get("pct_chg")
    chg_5d = latest.get("chg_5d")
    ma5, ma20 = ind.get("ma5"), ind.get("ma20")
    cross = ind.get("macd_cross")
    turnover = latest.get("turnover")

    reasons: list[str] = []
    phase, label, color = "unknown", "信号不明（建议观望）", "gray"

    if main_5d is None or pos_days is None:
        return {"phase": phase, "label": label, "color": color,
                "reasons": ["资金面数据不足，无法判断主力阶段"]}

    up_trend = (ma5 is not None and ma20 is not None and ma5 > ma20)

    # 离场/派发：主力持续净流出
    if main_5d < 0 and (pos_days is not None and pos_days <= 1):
        phase, label, color = "leaving", "疑似主力离场 / 派发", "green"
        reasons.append(f"近5日主力净流出 {abs(main_5d):.2f} 亿，净流入仅 {pos_days}/5 天")
        if chg_5d is not None and chg_5d < 0:
            reasons.append(f"近5日股价下跌 {chg_5d:.2f}%，量价配合走弱")
        if ma5 is not None and ma20 is not None and ma5 < ma20:
            reasons.append("MA5 下穿 MA20，短期均线转弱")
    # 启动：主力净流入 + 放量上涨 + 均线多头
    elif main_5d > 0 and pct_today is not None and pct_today > 3 and up_trend:
        phase, label, color = "launching", "疑似启动 / 拉升", "red"
        reasons.append(f"今日涨幅 {pct_today:.2f}%，近5日主力净流入 {main_5d:.2f} 亿")
        if cross == "golden":
            reasons.append("MACD 金叉，动能转强")
        if turnover is not None and turnover > 5:
            reasons.append(f"换手率 {turnover:.2f}%，量能放大")
    # 建仓/吸筹：主力持续净流入但股价温和（未明显拉升）
    elif main_5d > 0 and (pos_days is not None and pos_days >= 3) and (chg_5d is None or abs(chg_5d) < 8):
        phase, label, color = "building", "疑似主力建仓 / 吸筹", "orange"
        reasons.append(f"近5日主力净流入 {main_5d:.2f} 亿，净流入 {pos_days}/5 天")
        reasons.append(f"同期股价波动温和（近5日 {chg_5d if chg_5d is not None else 0:.2f}%），疑似低位收集筹码")
        if turnover is not None and turnover < 5:
            reasons.append(f"换手率 {turnover:.2f}%，未明显放量，符合吸筹特征")
    else:
        reasons.append(f"近5日主力净额 {main_5d:.2f} 亿、净流入 {pos_days}/5 天，多空交织，方向待确认")

    return {"phase": phase, "label": label, "color": color, "reasons": reasons}
