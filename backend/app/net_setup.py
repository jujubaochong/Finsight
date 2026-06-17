"""
网络设置 — 让数据抓取直连数据源，绕过系统/环境代理。

为什么需要：
  很多用户机器残留了已关闭梯子的代理（环境变量 HTTP(S)_PROXY，或 Windows
  系统级代理设置）。Python requests 在默认 trust_env=True 下会读取系统代理，
  导致 akshare 对东方财富/新浪的请求全部 ProxyError，从而 K线/资金流/板块/
  市场概览全部拉不到数据。

  单纯清环境变量对 Windows「系统级代理」无效，因此这里直接 monkey-patch
  requests.Session，将 trust_env 默认设为 False，并清空 proxies，从根上让所有
  通过 requests 发出的请求（akshare 内部即用 requests）忽略代理、直连。

如确需走代理：设环境变量 FINSIGHT_USE_SYSTEM_PROXY=1 即可恢复默认行为。
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def disable_system_proxy() -> None:
    if os.getenv("FINSIGHT_USE_SYSTEM_PROXY", "0") == "1":
        return

    # 1) 清理代理相关环境变量
    for var in (
        "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
        "ALL_PROXY", "all_proxy",
    ):
        os.environ.pop(var, None)
    # 放行所有域名，进一步兜底
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"

    # 2) 从最底层关闭代理探测：让 urllib/requests 永远拿到空代理。
    #    这是最彻底的一层 —— 即便某些库在 patch 之前就创建了 Session，
    #    实际发请求时仍会经过 getproxies()，返回空即不走代理。
    try:
        import urllib.request as _urlreq

        _urlreq.getproxies = lambda: {}  # type: ignore[assignment]
        _urlreq.getproxies_environment = lambda: {}  # type: ignore[assignment]
    except Exception as e:  # noqa: BLE001
        logger.warning("关闭 urllib 代理探测失败: %s", e)

    # 3) Monkey-patch requests：Session 默认不信任环境/系统代理，
    #    并把 requests.utils.getproxies 也置空（requests 内部用它合并代理）。
    try:
        import requests
        import requests.utils as _rutils
        import requests.sessions as _rsessions

        _rutils.getproxies = lambda: {}  # type: ignore[assignment]
        try:
            _rsessions.getproxies = lambda: {}  # type: ignore[assignment]
        except Exception:  # noqa: BLE001
            pass

        _orig_init = requests.Session.__init__

        def _patched_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            self.trust_env = False
            self.proxies = {}

        requests.Session.__init__ = _patched_init  # type: ignore[assignment]

        _orig_merge = requests.Session.merge_environment_settings

        def _patched_merge(self, url, proxies, stream, verify, cert):
            settings = _orig_merge(self, url, proxies, stream, verify, cert)
            settings["proxies"] = {}
            return settings

        requests.Session.merge_environment_settings = _patched_merge  # type: ignore[assignment]

        logger.info("已禁用系统/环境代理，数据抓取将直连数据源")
    except Exception as e:  # noqa: BLE001
        logger.warning("禁用系统代理失败（不影响启动）: %s", e)


def force_ipv4() -> None:
    """强制网络请求只走 IPv4。

    部分网络环境下 IPv6 到东方财富/新浪不通（连接被重置 RemoteDisconnected），
    而系统/curl 默认优先 IPv6，导致 akshare 请求失败。这里让 socket 的地址解析
    只返回 IPv4 结果，规避不通的 IPv6 路径。

    如需恢复默认（同时尝试 v4/v6）：设环境变量 FINSIGHT_ALLOW_IPV6=1。
    """
    if os.getenv("FINSIGHT_ALLOW_IPV6", "0") == "1":
        return
    try:
        import socket

        _orig_getaddrinfo = socket.getaddrinfo

        def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
            # 强制只解析 IPv4
            return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = _ipv4_only  # type: ignore[assignment]
        logger.info("已强制使用 IPv4 直连（规避不通的 IPv6 路径）")
    except Exception as e:  # noqa: BLE001
        logger.warning("强制 IPv4 失败（不影响启动）: %s", e)

    # urllib3 官方推荐的强制 IPv4 方式：requests 底层用 urllib3，
    # 它通过 allowed_gai_family() 决定地址族。直接让它只返回 AF_INET，
    # 比单独 patch socket 更可靠（双保险）。
    try:
        import socket as _socket
        import urllib3.util.connection as _u3conn

        _u3conn.allowed_gai_family = lambda: _socket.AF_INET  # type: ignore[assignment]
    except Exception as e:  # noqa: BLE001
        logger.warning("urllib3 IPv4 强制失败（不影响启动）: %s", e)



def curl_get_json(url: str, params: dict | None = None, timeout: int = 20):
    """用系统 curl 子进程抓取 JSON（绕过 Python 的 TLS 指纹被拦截问题）。

    背景：部分网络环境下，东方财富会主动重置 Python(urllib3/OpenSSL) 的连接
    （RemoteDisconnected），但系统 curl（Windows schannel TLS）可以正常访问。
    因此对这类被拦截的接口，改用 curl 子进程兜底抓取。

    返回解析后的 dict/list；失败返回 None。
    """
    import json
    import shutil
    import subprocess
    import urllib.parse

    curl_bin = shutil.which("curl")
    if not curl_bin:
        return None

    if params:
        # 东财参数里有 + 等字符，需正确编码；safe 保留逗号/冒号常见分隔符
        query = urllib.parse.urlencode(params, safe=":,+")
        url = f"{url}?{query}"

    try:
        proc = subprocess.run(
            [
                curl_bin, "-s", "--max-time", str(timeout),
                "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                "-H", "Accept: */*",
                url,
            ],
            capture_output=True, timeout=timeout + 5,
        )
        out = proc.stdout.decode("utf-8", errors="ignore").strip()
        if not out:
            return None
        # 东财部分接口返回 jsonp 包裹，去掉外层回调
        if out.startswith("(") and out.endswith(")"):
            out = out[1:-1]
        return json.loads(out)
    except Exception as e:  # noqa: BLE001
        logger.warning("curl 抓取失败 %s: %s", url, e)
        return None
