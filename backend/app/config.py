"""
应用配置
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # 数据库
    database_url: str = "sqlite:///./finsight.db"

    # AI
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # Redis (可选，用于缓存)
    redis_url: str = "redis://localhost:6379/0"

    # 应用
    secret_key: str = "change-me-in-production"
    debug: bool = True

    # 数据缓存 TTL（秒）
    cache_ttl_stock_list: int = 86400  # 股票列表缓存 24 小时
    cache_ttl_financials: int = 43200  # 财务数据缓存 12 小时
    cache_ttl_analysis: int = 3600  # AI 分析缓存 1 小时

    # AI 调用限制
    ai_max_retries: int = 3
    ai_request_timeout: int = 60


settings = Settings()
