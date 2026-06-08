# FinSight - AI 驱动的智能投研平台

![FinSight Logo](https://img.shields.io/badge/FinSight-AI投研平台-blue)
![Python](https://img.shields.io/badge/Python-3.9+-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-lightblue)
![React](https://img.shields.io/badge/React-18+-61dafb)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178c6)

## 🚀 项目简介

FinSight 是一个基于 AI 的智能投资研究平台，旨在为投资者提供数据驱动的股票分析、异动监控和行业对标功能。项目结合了实时数据获取、AI 分析和可视化界面，帮助用户做出更明智的投资决策。

## ✨ 核心功能

### 📊 股票数据分析
- **实时股票搜索**：支持 A 股股票代码/名称模糊搜索
- **财务数据获取**：从 AkShare 获取实时财务数据
- **AI 智能分析**：基于 DeepSeek API 的股票分析和投资建议
- **公告监控**：实时获取公司重要公告

### 🔔 智能异动监控
- **15+ 公告规则**：自动识别年报、季报、业绩预告等重要公告
- **财务异动检测**：监控营收、利润、负债率等关键指标变化
- **实时提醒系统**：自选股异动实时提醒
- **历史记录管理**：30天异动记录保留

### 📈 行业对标分析
- **行业基准计算**：自动计算行业均值、中位数、最大值等统计指标
- **同行业对比**：显示股票在行业中的排名和位置
- **同行股票列表**：展示同行业其他公司数据对比

### 🎨 现代化界面
- **响应式设计**：适配桌面和移动设备
- **实时图表**：财务数据可视化展示
- **用户体验优化**：搜索防抖、加载状态、错误提示

## 🏗️ 技术架构

### 后端 (FastAPI)
```
backend/
├── app/
│   ├── models/          # 数据模型
│   ├── schemas/         # Pydantic 模式
│   ├── routers/         # API 路由
│   ├── services/        # 业务逻辑
│   │   ├── data_fetcher.py      # 数据获取服务
│   │   ├── ai_analyzer.py       # AI 分析服务
│   │   ├── alert_monitor.py     # 异动监控服务
│   │   ├── industry_analyzer.py # 行业分析服务
│   │   └── report_generator.py  # 报告生成服务
│   ├── database.py      # 数据库连接
│   ├── config.py        # 配置管理
│   └── main.py          # 应用入口
├── requirements.txt     # Python 依赖
└── .env.example        # 环境变量示例
```

### 前端 (React + TypeScript)
```
frontend/
├── src/
│   ├── components/      # React 组件
│   ├── pages/          # 页面组件
│   ├── hooks/          # 自定义 Hooks
│   ├── services/       # API 服务
│   └── types/          # TypeScript 类型定义
├── public/             # 静态资源
└── package.json        # Node.js 依赖
```

## 🛠️ 快速开始

### 1. 环境要求
- Python 3.9+
- Node.js 18+
- Git

### 2. 后端设置
```bash
# 克隆项目
git clone https://github.com/yourusername/finsight.git
cd finsight/backend

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env 文件，添加你的 DeepSeek API 密钥

# 启动后端
uvicorn app.main:app --reload --port 8000
```

### 3. 前端设置
```bash
cd ../frontend

# 安装依赖
npm install

# 启动前端
npm run dev
```

### 4. 访问应用
- 前端界面：http://localhost:3001
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## 📁 项目结构

```
finsight/
├── docs/                    # 项目文档
│   ├── 01_产品愿景与目标.md
│   ├── 02_竞品研究.md
│   ├── 03_用户画像与核心场景.md
│   ├── 04_核心功能PRD.md
│   ├── 05_AI策略设计.md
│   ├── 06_原型草图.md
│   ├── 07_指标体系.md
│   └── 08_项目路线图.md
├── backend/                 # 后端代码（含 scripts/ 辅助脚本、tests/ 单元测试）
├── frontend/               # 前端代码
├── .gitignore             # Git 忽略文件
└── README.md              # 项目说明
```

## 🔧 配置说明

### 环境变量 (backend/.env)
```env
# AI API
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 数据库
DATABASE_URL=sqlite:///./finsight.db

# 缓存设置
CACHE_TTL_STOCK_LIST=3600
CACHE_TTL_FINANCIALS=1800
CACHE_TTL_INDUSTRY_BENCHMARKS=86400
```

### 数据源
- **AkShare**：A 股股票数据、财务数据、公告数据
- **DeepSeek API**：AI 分析和报告生成
- **SQLite**：本地数据存储（支持 PostgreSQL 扩展）

## 🚢 部署

### 开发环境
```bash
# 使用内置服务器
uvicorn app.main:app --reload --port 8000
npm run dev
```

### 生产环境建议
1. **使用 PostgreSQL** 替换 SQLite
2. **配置 Redis** 作为缓存
3. **使用 Nginx** 作为反向代理
4. **设置 SSL/TLS** 加密
5. **配置监控和日志**

## 📈 项目特色

### 技术亮点
- **端到端类型安全**：前端 TypeScript + 后端 Python 类型注解（Pydantic 校验）
- **异步任务调度**：后台定时数据更新与报告异步生成
- **智能缓存策略**：减少外部 API 调用，降低限流风险
- **健壮的数据层**：重试 + 指数退避 + 缓存 + 降级兜底
- **模块化设计**：服务分层，易于扩展和维护

### 业务价值
- **降低研究成本**：自动化数据收集和分析
- **提高决策质量**：数据驱动的投资建议
- **实时风险预警**：及时的市场异动提醒
- **行业对标分析**：全面的竞争态势评估

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

- 项目仓库：[https://github.com/yourusername/finsight](https://github.com/yourusername/finsight)
- 问题反馈：[Issues](https://github.com/yourusername/finsight/issues)

## 🙏 致谢

- [AkShare](https://github.com/akfamily/akshare) - 提供股票数据接口
- [DeepSeek](https://www.deepseek.com/) - 提供 AI 分析能力
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Python Web 框架
- [React](https://react.dev/) - 前端开发框架

---

**FinSight - 让投资更智能，让决策更简单** 🚀