# FinSight Backend

Python FastAPI 后端。

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入真实的 API Key

# 4. 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

## 项目结构

```
backend/
├── app/
│   ├── main.py           # FastAPI 应用入口
│   ├── config.py         # 配置管理
│   ├── models/           # SQLAlchemy ORM 模型
│   ├── routers/          # API 路由（Controller 层）
│   ├── services/         # 业务逻辑层
│   └── schemas/          # Pydantic 请求/响应模型
├── tests/
├── requirements.txt
└── .env.example
```

## API 文档

启动后访问 http://localhost:8000/docs 查看 Swagger 文档。
