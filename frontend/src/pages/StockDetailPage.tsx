/**
 * 股票详情页 — 核心页面
 * 优化：加入 loading skeleton、错误处理、自选状态同步
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useStockData } from '../hooks/useStockData'
import { addToWatchlist, removeFromWatchlist, generateReport, getWatchlist, refreshStockData } from '../services/api'
import AIAnalysis from '../components/AIAnalysis'
import FinancialCharts from '../components/FinancialCharts'
import IndustryComparison from '../components/IndustryComparison'
import SearchBar from '../components/SearchBar'

export default function StockDetailPage() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const { data, loading, error, refetch } = useStockData(code)
  const [inWatchlist, setInWatchlist] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [watchlistLoading, setWatchlistLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  // 检查是否已在自选
  useEffect(() => {
    if (!code) return
    getWatchlist()
      .then((items) => {
        setInWatchlist(items.some((i) => i.code === code))
      })
      .catch(() => {})
  }, [code])

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Skeleton */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-7 bg-gray-200 rounded w-32" />
            <div className="h-5 bg-gray-100 rounded w-20" />
          </div>
          <div className="h-4 bg-gray-100 rounded w-48 mt-2" />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
          <div className="h-5 bg-gray-200 rounded w-24 mb-4" />
          <div className="space-y-2">
            <div className="h-4 bg-gray-100 rounded w-full" />
            <div className="h-4 bg-gray-100 rounded w-4/5" />
            <div className="h-4 bg-gray-100 rounded w-3/5" />
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
          <div className="h-5 bg-gray-200 rounded w-24 mb-4" />
          <div className="h-64 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-20">
        <div className="text-5xl mb-4">📊</div>
        <p className="text-gray-500 text-lg mb-2">{error || '股票不存在或数据加载失败'}</p>
        <p className="text-gray-400 text-sm mb-6">
          请确认股票代码是否正确，或稍后重试
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            返回首页搜索
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
          >
            重试
          </button>
        </div>
      </div>
    )
  }

  const handleToggleWatchlist = async () => {
    setWatchlistLoading(true)
    try {
      if (inWatchlist) {
        await removeFromWatchlist(data.code)
        setInWatchlist(false)
      } else {
        await addToWatchlist(data.code)
        setInWatchlist(true)
      }
    } catch {
      // 静默失败
    } finally {
      setWatchlistLoading(false)
    }
  }

  const handleGenerateReport = async () => {
    setGenerating(true)
    try {
      const res = await generateReport(data.code)
      navigate(`/stock/${data.code}/report?task=${res.task_id}`)
    } catch {
      alert('报告生成失败，请重试')
    } finally {
      setGenerating(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await refreshStockData(data.code)
      await refetch()
    } catch {
      alert('数据刷新失败，请稍后重试')
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* 顶部搜索（方便切换股票） */}
      <div className="w-full max-w-md">
        <SearchBar size="normal" placeholder="搜索其他股票..." />
      </div>

      {/* 基本信息栏 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold text-gray-800">{data.name}</h1>
              <span className="text-lg text-gray-500 font-mono">{data.code}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded font-medium ${
                  data.market === 'SH'
                    ? 'bg-red-100 text-red-600'
                    : data.market === 'BJ'
                    ? 'bg-orange-100 text-orange-600'
                    : 'bg-blue-100 text-blue-600'
                }`}
              >
                {data.market === 'SH' ? '上交所' : data.market === 'BJ' ? '北交所' : '深交所'}
              </span>
            </div>
            <div className="flex gap-4 text-sm text-gray-500">
              {data.industry && <span>🏷️ {data.industry}</span>}
              {data.listing_date && <span>📅 {data.listing_date}</span>}
              {!data.is_active && (
                <span className="text-red-500 font-medium">⚠️ 已退市</span>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              title="重新拉取最新财务与公告数据"
              className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-600
                         hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {refreshing ? '⟳ 刷新中...' : '⟳ 刷新数据'}
            </button>
            <button
              onClick={handleToggleWatchlist}
              disabled={watchlistLoading}
              className={`px-4 py-2 text-sm rounded-lg transition-all ${
                inWatchlist
                  ? 'bg-yellow-50 border border-yellow-300 text-yellow-700 hover:bg-yellow-100'
                  : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
              } disabled:opacity-50`}
            >
              {watchlistLoading ? '...' : inWatchlist ? '★ 已自选' : '☆ 加入自选'}
            </button>
            <button
              onClick={handleGenerateReport}
              disabled={generating}
              className="px-5 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700
                         disabled:opacity-50 transition-colors font-medium"
            >
              {generating ? '⏳ 生成中...' : '📝 生成研报'}
            </button>
          </div>
        </div>
      </div>

      {/* AI 快速分析 */}
      <AIAnalysis analysis={data.quick_analysis} loading={false} />

      {/* 财务图表 */}
      <FinancialCharts financials={data.financials} />

      {/* 行业对标 */}
      {data.industry && <IndustryComparison code={data.code} />}

      {/* 近期公告 */}
      {data.announcements && data.announcements.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
            📋 近期公告
            <span className="text-xs font-normal text-gray-400">
              ({data.announcements.length}条)
            </span>
          </h2>
          <div className="space-y-1">
            {data.announcements.slice(0, 10).map((a) => (
              <div
                key={a.id}
                className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0
                           hover:bg-gray-50 rounded px-2 -mx-2 transition-colors"
              >
                <span className="text-xs text-gray-400 shrink-0 mt-0.5 font-mono">
                  {a.publish_date}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-700 leading-relaxed">{a.title}</p>
                  {a.summary && (
                    <p className="text-xs text-gray-400 mt-1">{a.summary}</p>
                  )}
                </div>
                {a.url && (
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-500 hover:underline shrink-0"
                    onClick={(e) => e.stopPropagation()}
                  >
                    原文
                  </a>
                )}
              </div>
            ))}
          </div>
          {data.announcements.length > 10 && (
            <p className="text-xs text-gray-400 text-center mt-3">
              仅展示最近10条公告
            </p>
          )}
        </div>
      )}

      {/* 底部操作区 */}
      <div className="flex justify-center gap-4 pb-8">
        <button
          onClick={handleGenerateReport}
          disabled={generating}
          className="px-8 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl
                     font-medium hover:from-blue-700 hover:to-blue-800
                     disabled:opacity-50 transition-all shadow-sm"
        >
          {generating ? '⏳ 正在生成报告...' : '📝 生成完整研究报告'}
        </button>
      </div>
    </div>
  )
}
