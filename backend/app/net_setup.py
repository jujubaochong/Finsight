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
