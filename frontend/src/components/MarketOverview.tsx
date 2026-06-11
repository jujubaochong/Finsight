/**
 * 首页市场概览：行业板块涨跌 + 主力净流入潜力股
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMarketOverview } from '../services/api'
import type { MarketOverview as Overview } from '../types/stock'

function pctColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'text-gray-400'
  return v >= 0 ? 'text-red-600' : 'text-green-600'
}

function pctText(v: number | null | undefined): string {
  if (v === null || v === undefined) return '--'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

export default function MarketOverview() {
  const navigate = useNavigate()
  const [data, setData] = useState<Overview | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getMarketOverview()
      .then((d) => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setData(null) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[0, 1].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="h-5 bg-gray-200 rounded w-28 mb-4 animate-pulse" />
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, j) => (
                <div key={j} className="h-8 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!data || (data.boards.length === 0 && data.potential.length === 0)) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 text-sm text-gray-500 flex items-center justify-between">
        <span>📡 市场概览数据暂时不可用（行情接口可能限频或非交易时段）</span>
        <button
          onClick={() => { setLoading(true); getMarketOverview().then(setData).catch(() => setData(null)).finally(() => setLoading(false)) }}
          className="px-3 py-1.5 text-xs rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50"
        >
          重新加载
        </button>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* 行业板块 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">🔥</span>
          <h3 className="font-semibold text-gray-800">热门板块</h3>
          <span className="text-xs text-gray-400">按涨幅排序</span>
        </div>
        <div className="space-y-1">
          {data.boards.map((b) => (
            <div key={b.name} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-gray-50">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm text-gray-700 truncate">{b.name}</span>
                {b.lead_stock && (
                  <span className="text-xs text-gray-400 truncate">领涨 {b.lead_stock}</span>
                )}
              </div>
              <span className={`text-sm font-semibold shrink-0 ${pctColor(b.pct_chg)}`}>
                {pctText(b.pct_chg)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 潜力股（主力净流入） */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">💰</span>
          <h3 className="font-semibold text-gray-800">主力净流入榜</h3>
          <span className="text-xs text-gray-400">强势且非追高</span>
        </div>
        <div className="space-y-1">
          {data.potential.map((s) => (
            <button
              key={s.code}
              onClick={() => navigate(`/stock/${s.code}`)}
              className="w-full flex items-center justify-between py-1.5 px-2 rounded hover:bg-blue-50 transition-colors text-left"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-medium text-gray-700 truncate">{s.name}</span>
                <span className="text-xs text-gray-400 font-mono">{s.code}</span>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-red-500">主力 +{s.main_net}亿</span>
                <span className={`text-sm font-semibold ${pctColor(s.pct_chg)}`}>{pctText(s.pct_chg)}</span>
              </div>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-gray-400 mt-2">※ 基于当日主力资金净流入，仅供研究，非投资建议</p>
      </div>
    </div>
  )
}
