/**
 * 应用根组件
 *
 * /                   → HomePage（搜索首页）
 * /stock/:code        → StockDetailPage（股票详情 + AI分析 + 行业对标）
 * /stock/:code/report → ReportPage（完整报告查看）
 * /watchlist          → WatchlistPage（自选股列表）
 * /alerts             → AlertsPage（异动监控）
 *
 * 页面采用按路由懒加载（React.lazy），首屏只加载首页与外壳，
 * 图表等较重依赖（recharts）仅在进入详情/报告页时按需加载。
 */
import { Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Layout from './components/Layout'

const HomePage = lazy(() => import('./pages/HomePage'))
const StockDetailPage = lazy(() => import('./pages/StockDetailPage'))
const ReportPage = lazy(() => import('./pages/ReportPage'))
const WatchlistPage = lazy(() => import('./pages/WatchlistPage'))
const AlertsPage = lazy(() => import('./pages/AlertsPage'))

function PageLoading() {
  return (
    <div className="flex items-center justify-center py-24 text-gray-400">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-300 border-t-blue-500" />
      <span className="ml-3 text-sm">加载中...</span>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route
          path="/"
          element={
            <Suspense fallback={<PageLoading />}>
              <HomePage />
            </Suspense>
          }
        />
        <Route
          path="/stock/:code"
          element={
            <Suspense fallback={<PageLoading />}>
              <StockDetailPage />
            </Suspense>
          }
        />
        <Route
          path="/stock/:code/report"
          element={
            <Suspense fallback={<PageLoading />}>
              <ReportPage />
            </Suspense>
          }
        />
        <Route
          path="/watchlist"
          element={
            <Suspense fallback={<PageLoading />}>
              <WatchlistPage />
            </Suspense>
          }
        />
        <Route
          path="/alerts"
          element={
            <Suspense fallback={<PageLoading />}>
              <AlertsPage />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  )
}
