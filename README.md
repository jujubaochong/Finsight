# FinSight — AI 智能投研助手

> 输入一个 A 股代码，获得 AI 自动生成的财务解读、风险提示和结构化研报。

## 项目概述

FinSight 解决的核心问题：个人投资者想研究股票基本面，但被工具门槛劝退。

- 🔍 **智能搜索**：支持代码、名称模糊搜索
- 🤖 **AI 快速分析**：10 秒内生成一句话总结 + 亮点/风险
- 📊 **财务可视化**：收入利润趋势、核心比率、增速对比
- 📝 **一键研报**：异步生成 5 章结构化研究报告
- ⭐ **自选管理**：关注股票，追踪变化

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + Recharts |
| 后端 | Python + FastAPI + SQLAlchemy + SQLite |
| AI | DeepSeek-V3 (OpenAI SDK 兼容) |
| 数据 | AkShare (A 股公开数据) |

## 快速开始

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY

# 启动
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:3000 即可使用。

## 项目结构

```
finsight/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── config.py        # 配置管理
│   │   ├── database.py      # 数据库连接
│   │   ├── cache.py         # 内存缓存
│   │   ├── logger.py        # 日志配置
│   │   ├── models/          # ORM 模型
│   │   ├── schemas/         # Pydantic 模型
│   │   ├── routers/         # API 路由
│   │   └── services/        # 业务逻辑
│   │       ├── ai_analyzer.py      # AI 分析（DeepSeek）
│   │       ├── data_fetcher.py     # 数据获取（AkShare）
│   │       └── report_generator.py # 报告编排
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # 通用组件
│   │   ├── pages/           # 页面组件
│   │   ├── hooks/           # 自定义 Hook
│   │   ├── services/        # API 封装
│   │   └── types/           # TypeScript 类型
│   └── package.json
└── docs/                    # 产品文档（PRD/设计/策略）
```

## API 概览

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/stocks/search?q=` | 搜索股票 |
| GET | `/api/stocks/{code}` | 获取详情 + AI 分析 |
| POST | `/api/reports/generate/{code}` | 生成研报 |
| GET | `/api/reports/status/{task_id}` | 查询生成进度 |
| GET | `/api/reports/{id}` | 获取报告内容 |
| GET | `/api/reports/list` | 报告列表 |
| GET | `/api/stocks/watchlist/list` | 获取自选列表 |
| POST | `/api/stocks/watchlist/add` | 添加自选 |
| DELETE | `/api/stocks/watchlist/{code}` | 删除自选 |
| GET | `/api/alerts/list` | 异动提醒列表 |
| POST | `/api/alerts/scan` | 手动触发异动扫描 |
| POST | `/api/alerts/read/{id}` | 标记已读 |
| GET | `/api/alerts/count` | 未读异动数 |
| GET | `/api/industry/comparison/{code}` | 行业对标分析 |
| GET | `/api/industry/peers/{code}` | 同行业股票列表 |
| GET | `/api/industry/list` | 行业列表 |

## 配置说明

核心配置项（`.env` 文件）：

- `DEEPSEEK_API_KEY`：必填，DeepSeek AI 的 API Key
- `DATABASE_URL`：数据库连接串，默认 SQLite
- `CACHE_TTL_ANALYSIS`：AI 分析缓存时间，默认 1 小时

## 开发状态

- [x] MVP 核心功能完成
- [x] 搜索 + 详情 + AI 分析 + 报告生成
- [x] 自选股管理
- [x] 异动监控（公告/股东/监管/财务异动规则引擎）
- [x] 行业对标分析（同行排名 + 指标对比图表）
- [ ] 用户系统（注册/登录）
- [ ] 移动端适配
- [ ] 批量赛道扫描
