/**
 * 技术面 + 资金面面板
 * - 顶部指标卡片（MA / MACD / KDJ / RSI / 主力资金信号）
 * - 价格 + MACD 副图
 * - 主力资金流柱状图
 * - 龙虎榜（可选）
 */
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, BarChart, Cell,
} from 'recharts'
import type { MarketSnapshot } from '../types/stock'

interface Props {
  snapshot: MarketSnapshot | null
  loading: boolean
}

function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return '--'
  return n.toFixed(digits)
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'up' | 'down' | 'normal' }) {
  const color = tone === 'up' ? 'text-red-600' : tone === 'down' ? 'text-green-600' : 'text-gray-800'
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-sm font-semibold ${color}`}>{value}</div>
    </div>
  )
}

export default function TechnicalPanel({ snapshot, loading }: Props) {
  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="h-5 bg-gray-200 rounded w-32 animate-pulse mb-4" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
        <div className="h-48 bg-gray-100 rounded animate-pulse" />
      </div>
    )
  }

  if (!snapshot || (!snapshot.indicators?.series?.length && !snapshot.fund_flow?.series?.length)) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 text-gray-400">
          <span className="text-lg">📈</span>
          <span className="text-sm">技术/资金数据暂时不可用（行情接口可能限频，请稍后刷新）</span>
        </div>
      </div>
    )
  }

  const ind = snapshot.indicators || {}
  const ff = snapshot.fund_flow || {}
  const latest = snapshot.latest || {}

  const maTone = (ind.ma5 ?? 0) > (ind.ma20 ?? 0) ? 'up' : 'down'
  const crossLabel = ind.macd_cross === 'golden' ? '金叉' : ind.macd_cross === 'dead' ? '死叉' : '—'
  const crossTone = ind.macd_cross === 'golden' ? 'up' : ind.macd_cross === 'dead' ? 'down' : 'normal'

  const fundTone =
    ff.signal === 'accumulate' ? 'text-red-600 bg-red-50 border-red-100'
    : ff.signal === 'distribute' ? 'text-green-700 bg-green-50 border-green-100'
    : 'text-gray-600 bg-gray-50 border-gray-100'

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-6 pt-5 pb-2 flex items-center gap-2">
        <span className="text-lg">📈</span>
        <h2 className="font-semibold text-gray-800">技术面 · 资金面</h2>
        <span className="text-xs bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full">日线数据 · 仅供研判</span>
      </div>

      {/* 指标卡片 */}
      <div className="px-6 grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        <Stat label="最新价" value={fmt(latest.close)} tone={(latest.pct_chg ?? 0) >= 0 ? 'up' : 'down'} />
        <Stat label="当日涨跌" value={`${fmt(latest.pct_chg)}%`} tone={(latest.pct_chg ?? 0) >= 0 ? 'up' : 'down'} />
        <Stat label="近5日涨跌" value={`${fmt(latest.chg_5d)}%`} tone={(latest.chg_5d ?? 0) >= 0 ? 'up' : 'down'} />
        <Stat label="换手率" value={`${fmt(latest.turnover)}%`} />
        <Stat label="MA5/MA20" value={`${fmt(ind.ma5)} / ${fmt(ind.ma20)}`} tone={maTone} />
        <Stat label="MACD" value={`${crossLabel} (${fmt(ind.macd)})`} tone={crossTone} />
        <Stat label="KDJ-J" value={fmt(ind.kdj_j)} tone={(ind.kdj_j ?? 50) > 80 ? 'up' : (ind.kdj_j ?? 50) < 20 ? 'down' : 'normal'} />
        <Stat label="RSI" value={fmt(ind.rsi)} tone={(ind.rsi ?? 50) > 70 ? 'up' : (ind.rsi ?? 50) < 30 ? 'down' : 'normal'} />
      </div>

      {/* 主力资金信号横幅 */}
      {ff.label && (
        <div className="px-6 mb-4">
          <div className={`rounded-lg px-4 py-2.5 border text-sm font-medium ${fundTone}`}>
            主力资金：{ff.label}
            <span className="text-xs font-normal ml-2 opacity-80">
              近5日主力净额 {fmt(ff.main_net_5d)} 亿 · 净流入 {ff.positive_days_5d ?? 0}/5 天
            </span>
          </div>
        </div>
      )}

      {/* 价格 + MACD 副图 */}
      {ind.series && ind.series.length > 0 && (
        <div className="px-4 pb-2">
          <div className="text-xs text-gray-500 px-2 mb-1">收盘价走势（近60日）</div>
          <ResponsiveContainer width="100%" height={180}>
            <ComposedChart data={ind.series} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.ceil(ind.series.length / 6)} />
              <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} width={44} />
              <Tooltip contentStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="close" name="收盘价" stroke="#2563eb" dot={false} strokeWidth={1.5} />
            </ComposedChart>
          </ResponsiveContainer>
          <div className="text-xs text-gray-500 px-2 mb-1 mt-2">MACD</div>
          <ResponsiveContainer width="100%" height={120}>
            <ComposedChart data={ind.series} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.ceil(ind.series.length / 6)} />
              <YAxis tick={{ fontSize: 10 }} width={44} />
              <Tooltip contentStyle={{ fontSize: 12 }} />
              <ReferenceLine y={0} stroke="#999" />
              <Bar dataKey="macd" name="MACD柱">
                {ind.series.map((d, i) => (
                  <Cell key={i} fill={d.macd >= 0 ? '#ef4444' : '#16a34a'} />
                ))}
              </Bar>
              <Line type="monotone" dataKey="dif" name="DIF" stroke="#f59e0b" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="dea" name="DEA" stroke="#8b5cf6" dot={false} strokeWidth={1} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 主力资金流柱状图 */}
      {ff.series && ff.series.length > 0 && (
        <div className="px-4 pb-3">
          <div className="text-xs text-gray-500 px-2 mb-1 mt-2">主力净流入（亿元，近20日）</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={ff.series} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.ceil(ff.series.length / 6)} />
              <YAxis tick={{ fontSize: 10 }} width={44} />
              <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: number) => [`${v} 亿`, '主力净额']} />
              <ReferenceLine y={0} stroke="#999" />
              <Bar dataKey="main_net" name="主力净额">
                {ff.series.map((d, i) => (
                  <Cell key={i} fill={d.main_net >= 0 ? '#ef4444' : '#16a34a'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 龙虎榜 */}
      {snapshot.lhb && snapshot.lhb.length > 0 && (
        <div className="px-6 pb-5">
          <div className="text-xs text-gray-500 mb-2">近期龙虎榜</div>
          <div className="space-y-1.5">
            {snapshot.lhb.slice(0, 5).map((l, i) => (
              <div key={i} className="text-xs bg-gray-50 rounded px-3 py-2 border border-gray-100">
                <span className="text-gray-500">{l.date}</span>
                <span className="ml-2 text-gray-800">{l.reason}</span>
                {l.net_buy !== null && (
                  <span className={`ml-2 ${l.net_buy >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                    净买 {(l.net_buy / 1e8).toFixed(2)} 亿
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
