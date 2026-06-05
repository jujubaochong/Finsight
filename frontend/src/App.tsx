/**
 * 应用根组件
 *
 * /                   → HomePage（搜索首页）
 * /stock/:code        → StockDetailPage（股票详情 + AI分析 + 行业对标）
 * /stock/:code/report → ReportPage（完整报告查看）
 * /watchlist          → WatchlistPage（自选股列表）
 * /alerts             → AlertsPage（异动监控）
 */
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import StockDetailPage from './pages/StockDetailPage'
import ReportPage from './pages/ReportPage'
import WatchlistPage from './pages/WatchlistPage'
import AlertsPage from './pages/AlertsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/stock/:code" element={<StockDetailPage />} />
        <Route path="/stock/:code/report" element={<ReportPage />} />
        <Route path="/watchlist" element={<WatchlistPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
      </Route>
    </Routes>
  )
}
