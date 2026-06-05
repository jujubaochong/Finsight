/**
 * 行业对标分析组件 — 展示目标股票在同行业中的位置
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getIndustryComparison } from '../services/api'
import type { IndustryComparison as IndustryComparisonType } from '../types/stock'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

interface Props {
  code: string
}

const METRIC_LABELS: Record<string, string> = {
  net_margin: '净利率(%)',
  roe: 'ROE(%)',
  debt_ratio: '资产负债率(%)',
  revenue_growth_yoy: '营收增速(%)',
  profit_growth_yoy: '利润增速(%)',
}

export default function IndustryComparison({ code }: Props) {
  const navigate = useNavigate()
  const [data, setData] = useState<IndustryComparisonType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedMetric, setSelectedMetric] = useState<string>('roe')

  useEffect(() => {
    if (!code) return
    setLoading(true)
    setError(null)
    getIndustryComparison(code)
      .then((result) => {
        if (result.error && !result.target_metrics) {
          setError(result.error)
        } else {
          setData(result)
        }
      })
      .catch((e) => setError(e.response?.data?.detail || '获取行业对标数据失败'))
      .finally(() => setLoading(false))
  }, [code])

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="h-5 bg-gray-200 rounded w-32 mb-4 animate-pulse" />
        <div className="h-48 bg-gray-100 rounded animate-pulse" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-800 mb-2 flex items-center gap-2">
          🏭 行业对标
        </h2>
        <p className="text-sm text-gray-400">{error}</p>
      </div>
    )
  }

  if (!data) return null

  const { target_metrics, industry_stats, rankings, top_peers } = data

  // 构建排名卡片数据
  const rankCards = Object.entries(rankings).map(([metric, ranking]) => ({
    metric,
    label: METRIC_LABELS[metric] || metric,
    ...ranking,
    value: target_metrics[metric as keyof typeof target_metrics] as number | null,
    industryAvg: industry_stats[metric]?.avg,
  }))

  // 构建同行对比图表数据
  const chartMetricData = top_peers
    .filter((p) => p[selectedMetric as keyof typeof p] != null)
    .map((p) => ({
      name: p.name.length > 4 ? p.name.slice(0, 4) + '..' : p.name,
      fullName: p.name,
      code: p.code,
      value: p[selectedMetric as keyof typeof p] as number,
      isTarget: p.code === code,
    }))
    .sort((a, b) => (b.value || 0) - (a.value || 0))
    .slice(0, 12)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="font-semibold text-gray-800 flex items-center gap-2">
          🏭 行业对标
          <span className="text-sm font-normal text-gray-400">
            {data.industry} · {data.peer_count}家同行
          </span>
        </h2>
      </div>

      {/* 排名卡片 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        {rankCards.map((card) => (
          <div
            key={card.metric}
            className={`rounded-lg p-3 cursor-pointer transition-all border ${
              selectedMetric === card.metric
                ? 'border-blue-300 bg-blue-50'
                : 'border-gray-100 bg-gray-50 hover:border-gray-200'
            }`}
            onClick={() => setSelectedMetric(card.metric)}
          >
            <div className="text-xs text-gray-500 mb-1">{card.label}</div>
            <div className="flex items-end gap-1">
              <span className="text-lg font-semibold text-gray-800">
                {card.value != null ? card.value.toFixed(1) : '—'}
              </span>
            </div>
            <div className="flex items-center gap-1 mt-1">
              <span
                className={`text-xs font-medium ${
                  card.percentile >= 70
                    ? 'text-emerald-600'
                    : card.percentile >= 40
                    ? 'text-gray-600'
                    : 'text-red-500'
                }`}
              >
                排名 {card.rank}/{card.total}
              </span>
              {card.industryAvg != null && (
                <span className="text-xs text-gray-400">
                  均值{card.industryAvg.toFixed(1)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 同行对比柱状图 */}
      {chartMetricData.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm text-gray-600 mb-3">
            {METRIC_LABELS[selectedMetric] || selectedMetric} — 同行对比
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartMetricData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} unit="%" />
              <Tooltip
                formatter={(value: any) => [`${Number(value).toFixed(2)}%`, METRIC_LABELS[selectedMetric]]}
                labelFormatter={(label: any, payload: any) => payload?.[0]?.payload?.fullName || label}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chartMetricData.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={entry.isTarget ? '#3b82f6' : '#e5e7eb'}
                    stroke={entry.isTarget ? '#2563eb' : 'none'}
                    strokeWidth={entry.isTarget ? 2 : 0}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-gray-400 text-center">
            蓝色柱 = 当前股票 · 灰色柱 = 同行业公司
          </p>
        </div>
      )}

      {/* 同行列表 */}
      <div>
        <h3 className="text-sm font-medium text-gray-600 mb-3">同行业主要公司</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 px-2 text-gray-500 font-medium">公司</th>
                <th className="text-right py-2 px-2 text-gray-500 font-medium">营收(亿)</th>
                <th className="text-right py-2 px-2 text-gray-500 font-medium">净利率</th>
                <th className="text-right py-2 px-2 text-gray-500 font-medium">ROE</th>
                <th className="text-right py-2 px-2 text-gray-500 font-medium">营收增速</th>
              </tr>
            </thead>
            <tbody>
              {top_peers.slice(0, 8).map((peer) => (
                <tr
                  key={peer.code}
                  className={`border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors ${
                    peer.code === code ? 'bg-blue-50 font-medium' : ''
                  }`}
                  onClick={() => navigate(`/stock/${peer.code}`)}
                >
                  <td className="py-2 px-2">
                    <span className="text-gray-800">{peer.name}</span>
                    {peer.code === code && (
                      <span className="ml-1 text-blue-500 text-[10px]">← 当前</span>
                    )}
                  </td>
                  <td className="text-right py-2 px-2 text-gray-600">
                    {peer.revenue?.toFixed(1) ?? '—'}
                  </td>
                  <td className="text-right py-2 px-2 text-gray-600">
                    {peer.net_margin != null ? `${peer.net_margin.toFixed(1)}%` : '—'}
                  </td>
                  <td className="text-right py-2 px-2 text-gray-600">
                    {peer.roe != null ? `${peer.roe.toFixed(1)}%` : '—'}
                  </td>
                  <td className="text-right py-2 px-2">
                    {peer.revenue_growth_yoy != null ? (
                      <span
                        className={
                          peer.revenue_growth_yoy >= 0 ? 'text-emerald-600' : 'text-red-500'
                        }
                      >
                        {peer.revenue_growth_yoy >= 0 ? '+' : ''}
                        {peer.revenue_growth_yoy.toFixed(1)}%
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
