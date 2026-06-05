/**
 * 财务图表组件
 * 优化：更好的数据格式化、空状态处理、响应式布局
 */
import { useState, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, ComposedChart, Area,
} from 'recharts'
import type { FinancialItem } from '../types/stock'

interface Props {
  financials: FinancialItem[]
}

type ViewMode = 'quarterly' | 'yearly'
type ChartTab = 'revenue' | 'ratio' | 'growth'

export default function FinancialCharts({ financials }: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>('quarterly')
  const [showTable, setShowTable] = useState(false)
  const [chartTab, setChartTab] = useState<ChartTab>('revenue')

  if (!financials || financials.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
        <div className="text-3xl mb-3">📊</div>
        <p className="text-gray-400">暂无财务数据</p>
        <p className="text-xs text-gray-300 mt-1">数据加载中或该股票无历史财务数据</p>
      </div>
    )
  }

  // 数据过滤与排序
  const filtered = useMemo(() => {
    const sorted = [...financials].sort((a, b) =>
      a.report_period.localeCompare(b.report_period)
    )
    if (viewMode === 'yearly') {
      return sorted.filter((f) => f.report_period.endsWith('Q4'))
    }
    return sorted.slice(-8)
  }, [financials, viewMode])

  // 图表数据
  const chartData = useMemo(
    () =>
      filtered.map((f) => ({
        period: f.report_period,
        营业收入: f.revenue ? Number(f.revenue.toFixed(2)) : null,
        净利润: f.net_profit ? Number(f.net_profit.toFixed(2)) : null,
        经营现金流: f.operating_cash_flow ? Number(f.operating_cash_flow.toFixed(2)) : null,
      })),
    [filtered]
  )

  const ratioData = useMemo(
    () =>
      filtered.map((f) => ({
        period: f.report_period,
        净利率: f.net_margin ?? null,
        ROE: f.roe ?? null,
        资产负债率: f.debt_ratio ?? null,
      })),
    [filtered]
  )

  const growthData = useMemo(
    () =>
      filtered
        .filter((f) => f.revenue_growth_yoy != null || f.profit_growth_yoy != null)
        .map((f) => ({
          period: f.report_period,
          营收增速: f.revenue_growth_yoy ?? null,
          利润增速: f.profit_growth_yoy ?? null,
        })),
    [filtered]
  )

  // 最新一期数据（用于指标卡）
  const latest = filtered[filtered.length - 1]

  // 自定义 tooltip 格式化
  const formatTooltipValue = (value: any, name: string) => {
    if (value == null) return ['—', name]
    const num = Number(value)
    if (isNaN(num)) return [String(value), name]
    if (name.includes('率') || name.includes('增速') || name === 'ROE') {
      return [`${num.toFixed(2)}%`, name]
    }
    return [`${num.toFixed(2)} 亿`, name]
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      {/* 头部：标题 + 视图切换 */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
        <h2 className="font-semibold text-gray-800">📊 财务数据</h2>
        <div className="flex gap-1.5">
          <button
            onClick={() => setViewMode('quarterly')}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              viewMode === 'quarterly'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            季度
          </button>
          <button
            onClick={() => setViewMode('yearly')}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              viewMode === 'yearly'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            年度
          </button>
          <span className="w-px bg-gray-200 mx-1" />
          <button
            onClick={() => setShowTable(!showTable)}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              showTable
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            表格
          </button>
        </div>
      </div>

      {/* 核心指标卡片 */}
      {latest && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
          {[
            { label: '营业收入', value: latest.revenue, unit: '亿', color: 'blue' },
            { label: '净利润', value: latest.net_profit, unit: '亿', color: 'emerald' },
            { label: '净利率', value: latest.net_margin, unit: '%', color: 'purple' },
            { label: 'ROE', value: latest.roe, unit: '%', color: 'amber' },
            { label: '资产负债率', value: latest.debt_ratio, unit: '%', color: 'red' },
          ].map((item) => (
            <div key={item.label} className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">{item.label}</div>
              <div className="text-lg font-semibold text-gray-800">
                {item.value != null ? (
                  <>
                    {item.value >= 1000
                      ? item.value.toFixed(0)
                      : item.value >= 100
                      ? item.value.toFixed(1)
                      : item.value.toFixed(2)}
                    <span className="text-xs text-gray-400 ml-0.5">{item.unit}</span>
                  </>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </div>
              {/* 同比变化（如果有） */}
              {item.label === '营业收入' && latest.revenue_growth_yoy != null && (
                <div
                  className={`text-xs mt-0.5 ${
                    latest.revenue_growth_yoy >= 0 ? 'text-emerald-600' : 'text-red-500'
                  }`}
                >
                  同比 {latest.revenue_growth_yoy >= 0 ? '+' : ''}
                  {latest.revenue_growth_yoy.toFixed(1)}%
                </div>
              )}
              {item.label === '净利润' && latest.profit_growth_yoy != null && (
                <div
                  className={`text-xs mt-0.5 ${
                    latest.profit_growth_yoy >= 0 ? 'text-emerald-600' : 'text-red-500'
                  }`}
                >
                  同比 {latest.profit_growth_yoy >= 0 ? '+' : ''}
                  {latest.profit_growth_yoy.toFixed(1)}%
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showTable ? (
        /* 表格视图 */
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2.5 px-3 text-gray-500 font-medium text-xs">报告期</th>
                <th className="text-right py-2.5 px-3 text-gray-500 font-medium text-xs">营收(亿)</th>
                <th className="text-right py-2.5 px-3 text-gray-500 font-medium text-xs">净利润(亿)</th>
                <th className="text-right py-2.5 px-3 text-gray-500 font-medium text-xs">净利率(%)</th>
                <th className="text-right py-2.5 px-3 text-gray-500 font-medium text-xs">ROE(%)</th>
                <th className="text-right py-2.5 px-3 text-gray-500 font-medium text-xs">经营现金流(亿)</th>
                <th className="text-right py-2.5 px-3 text-gray-500 font-medium text-xs">营收增速(%)</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((f) => (
                <tr
                  key={f.report_period}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="py-2.5 px-3 font-medium text-gray-700">{f.report_period}</td>
                  <td className="text-right py-2.5 px-3 text-gray-600">
                    {f.revenue?.toFixed(2) ?? '—'}
                  </td>
                  <td className="text-right py-2.5 px-3 text-gray-600">
                    {f.net_profit?.toFixed(2) ?? '—'}
                  </td>
                  <td className="text-right py-2.5 px-3 text-gray-600">
                    {f.net_margin?.toFixed(2) ?? '—'}
                  </td>
                  <td className="text-right py-2.5 px-3 text-gray-600">
                    {f.roe?.toFixed(2) ?? '—'}
                  </td>
                  <td className="text-right py-2.5 px-3 text-gray-600">
                    {f.operating_cash_flow?.toFixed(2) ?? '—'}
                  </td>
                  <td className="text-right py-2.5 px-3">
                    {f.revenue_growth_yoy != null ? (
                      <span
                        className={
                          f.revenue_growth_yoy >= 0 ? 'text-emerald-600' : 'text-red-500'
                        }
                      >
                        {f.revenue_growth_yoy >= 0 ? '+' : ''}
                        {f.revenue_growth_yoy.toFixed(1)}
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
      ) : (
        /* 图表视图 */
        <div>
          {/* 图表 Tab 切换 */}
          <div className="flex gap-1 mb-4 border-b border-gray-100 pb-2">
            {[
              { key: 'revenue' as ChartTab, label: '收入利润' },
              { key: 'ratio' as ChartTab, label: '核心比率' },
              { key: 'growth' as ChartTab, label: '增速趋势' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setChartTab(tab.key)}
                className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
                  chartTab === tab.key
                    ? 'text-blue-700 bg-blue-50 font-medium'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* 收入利润图表 */}
          {chartTab === 'revenue' && (
            <div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                  <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} />
                  <Tooltip formatter={formatTooltipValue} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="营业收入" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="净利润" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="经营现金流" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-xs text-gray-400 text-center mt-1">单位：亿元</p>
            </div>
          )}

          {/* 核心比率图表 */}
          {chartTab === 'ratio' && (
            <div>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={ratioData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                  <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} unit="%" />
                  <Tooltip formatter={formatTooltipValue} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    type="monotone"
                    dataKey="净利率"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="ROE"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="资产负债率"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    strokeDasharray="5 5"
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
              <p className="text-xs text-gray-400 text-center mt-1">单位：%</p>
            </div>
          )}

          {/* 增速趋势图表 */}
          {chartTab === 'growth' && (
            <div>
              {growthData.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={280}>
                    <ComposedChart data={growthData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                      <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} unit="%" />
                      <Tooltip formatter={formatTooltipValue} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Area
                        type="monotone"
                        dataKey="营收增速"
                        fill="#dbeafe"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        connectNulls
                      />
                      <Line
                        type="monotone"
                        dataKey="利润增速"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        connectNulls
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                  <p className="text-xs text-gray-400 text-center mt-1">同比增速（%）</p>
                </>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                  暂无足够数据计算增速
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
