/**
 * 首页 — 搜索入口
 * 优化：使用新的 SearchBar 组件，加入最近浏览和热门推荐
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import SearchBar, { getRecentSearches } from '../components/SearchBar'
import MarketOverview from '../components/MarketOverview'
import type { StockBrief } from '../types/stock'

const HOT_STOCKS: StockBrief[] = [
  { code: '600519', name: '贵州茅台', market: 'SH' },
  { code: '000001', name: '平安银行', market: 'SZ' },
  { code: '300750', name: '宁德时代', market: 'SZ' },
  { code: '002594', name: '比亚迪', market: 'SZ' },
  { code: '603259', name: '药明康德', market: 'SH' },
  { code: '000858', name: '五粮液', market: 'SZ' },
]

export default function HomePage() {
  const navigate = useNavigate()
  const [recentSearches, setRecentSearches] = useState<StockBrief[]>([])

  useEffect(() => {
    setRecentSearches(getRecentSearches())
  }, [])

  return (
    <div className="flex flex-col items-center py-16 px-4 min-h-[70vh]">
      {/* 品牌标题 */}
      <div className="text-center mb-10">
        <h1 className="text-4xl font-bold text-gray-800 mb-3">
          <span className="text-blue-600">Fin</span>Sight
        </h1>
        <p className="text-gray-500 text-lg">
          AI 驱动的智能投研助手 — 输入代码，看懂一家公司
        </p>
      </div>

      {/* 搜索框 */}
      <div className="w-full max-w-xl mb-10">
        <SearchBar autoFocus size="large" />
      </div>

      {/* 最近浏览 */}
      {recentSearches.length > 0 && (
        <div className="w-full max-w-xl mb-8">
          <p className="text-sm text-gray-400 mb-3">最近浏览</p>
          <div className="flex flex-wrap gap-2">
            {recentSearches.map((s) => (
              <button
                key={s.code}
                onClick={() => navigate(`/stock/${s.code}`)}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200
                           rounded-lg text-sm hover:border-blue-300 hover:shadow-sm transition-all"
              >
                <span className="font-medium text-gray-700">{s.name}</span>
                <span className="text-xs text-gray-400">{s.code}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 热门推荐 */}
      <div className="w-full max-w-xl">
        <p className="text-sm text-gray-400 mb-3">
          {recentSearches.length > 0 ? '热门股票' : '试试这些'}
        </p>
        <div className="flex flex-wrap gap-2 justify-start">
          {HOT_STOCKS.map((s) => (
            <button
              key={s.code}
              onClick={() => navigate(`/stock/${s.code}`)}
              className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm
                         hover:border-blue-300 hover:text-blue-600 transition-colors shadow-sm"
            >
              {s.name}
              <span className="text-xs text-gray-400 ml-1">{s.code}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 市场概览：板块 + 主力净流入潜力股 */}
      <div className="w-full max-w-4xl mt-12">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">📊 市场概览</h2>
          <span className="text-xs text-gray-400">实时行情 · 数据来源 AkShare</span>
        </div>
        <MarketOverview />
      </div>

      {/* 底部说明 */}
      <div className="mt-auto pt-16 text-center">
        <div className="flex items-center gap-6 text-xs text-gray-400">
          <span>📊 财务数据自动聚合</span>
          <span>🤖 AI 智能分析</span>
          <span>📝 一键生成研报</span>
        </div>
      </div>
    </div>
  )
}
