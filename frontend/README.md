# FinSight Frontend

React + TypeScript + TailwindCSS + Recharts 前端。

## 快速开始

```bash
npm install
npm run dev
```

访问 http://localhost:3000

## 项目结构

```
frontend/
├── index.html
├── src/
│   ├── index.tsx              # 应用入口
│   ├── App.tsx                # 路由配置
│   ├── index.css              # 全局样式 + Tailwind
│   ├── pages/                 # 页面组件（对应路由）
│   │   ├── HomePage.tsx       # 搜索首页
│   │   ├── StockDetailPage.tsx # 股票详情（核心页面）
│   │   ├── ReportPage.tsx     # 报告查看
│   │   └── WatchlistPage.tsx  # 自选股列表
│   ├── components/            # 可复用组件
│   │   ├── Layout.tsx         # 全局布局（导航栏）
│   │   ├── SearchBar.tsx      # 搜索栏
│   │   ├── StockCard.tsx      # 股票卡片
│   │   ├── AIAnalysis.tsx     # AI 分析展示
│   │   └── FinancialCharts.tsx # 财务图表
│   ├── services/
│   │   └── api.ts             # API 请求封装
│   ├── hooks/
│   │   └── useStockData.ts    # 股票数据 hook
│   └── types/
│       └── stock.ts           # TypeScript 类型定义
├── vite.config.ts
├── tsconfig.json
└── package.json
```
