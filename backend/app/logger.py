"""
日志配置
"""
import logging
import sys

from app.config import settings


def setup_logging():
    """配置应用日志"""
    level = logging.DEBUG if settings.debug else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # 根 logger
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # 降低第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("akshare").setLevel(logging.WARNING)

    return root
