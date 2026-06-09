"""pytest 公共 fixture"""
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 确保可以 import app.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.cache import cache
from app.models.stock import Base, Stock


@pytest.fixture()
def db():
    """每个测试一个独立的内存数据库会话"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个测试前后清空内存缓存，避免缓存串扰"""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """禁用数据获取层的 sleep，加速测试"""
    monkeypatch.setattr("app.services.data_fetcher.time.sleep", lambda *a, **k: None)


@pytest.fixture()
def sample_stock(db):
    """插入一只样本股票"""
    stock = Stock(code="600519", name="贵州茅台", market="SH")
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock
