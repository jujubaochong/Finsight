/**
 * 决策对照台
 * - 客观风险/收益预估（止损位、目标位、赔率、波动率），自动加载、无AI
 * - 用户先填自己的预期（方向 + 周期），点"对照AI"
 * - AI 给出独立判断 + 长短线倾向 + 风险收益解读，并高亮与用户预期是否一致
 *
 * 定位：AI 不替你决策，而是作为对照镜子，帮你发现自己判断的分歧与盲点。
 */
import { useEffect, useState } from 'react'
import { getDecisionSnapshot, compareDecision } from '../services/api'
import type { DecisionSnapshot, DecisionResult } from '../types/stock'

interface Props {
  code: string
}

type Direction = 'bullish' | 'bearish' | 'unsure'
type Horizon = 'long' | 'short' | 'unsure'

const DIR_LABEL: Record<Direction, string> = { bullish: '看多', bearish: '看空', unsure: '不确定' }
const HOR_LABEL: Record<Horizon, string> = { long: '长线', short: '短线', unsure: '未定' }

function fmt(n: number | null | undefined, suffix = ''): string {
  if (n === null || n === undefined) return '--'
  return `${n}${suffix}`
}

function consistencyStyle(c: string): { cls: string; icon: string } {
  if (c.includes('一致') && !c.includes('部分')) return { cls: 'bg-green-50 text-green-700 border-green-200', icon: '✅' }
  if (c.includes('部分')) return { cls: 'bg-amber-50 text-amber-700 border-amber-200', icon: '〽️' }
  if (c.includes('分歧')) return { cls: 'bg-red-50 text-red-700 border-red-200', icon: '⚠️' }
  return { cls: 'bg-gray-50 text-gray-600 border-gray-200', icon: 'ℹ️' }
}

export default function DecisionBoard({ code }: Props) {
  const [snap, setSnap] = useState<DecisionSnapshot | null>(null)
  const [snapLoading, setSnapLoading] = useState(true)

  const [direction, setDirection] = useState<Direction>('unsure')
  const [horizon, setHorizon] = useState<Horizon>('unsure')

  const [decision, setDecision] = useState<DecisionResult | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  // 客观风险/收益：进入即异步加载
  useEffect(() => {
    if (!code) return
    let cancelled = false
    setSnap(null)
    setDecision(null)
    setSnapLoading(true)
    getDecisionSnapshot(code)
      .then((d) => { if (!cancelled) setSnap(d) })
      .catch(() => { if (!cancelled) setSnap(null) })
      .finally(() => { if (!cancelled) setSnapLoading(false) })
    return () => { cancelled = true }
  }, [code])

  const handleCompare = async () => {
    setAiLoading(true)
    setDecision(null)
    try {
      const res = await compareDecision(code, direction, horizon)
      setDecision(res.decision)
    } catch {
      setDecision(null)
    } finally {
      setAiLoading(false)
    }
  }

  const rr = snap?.risk_reward
  const hasRR = rr && rr.price !== undefined && rr.price !== null

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-6 pt-5 pb-3 flex items-center gap-2">
        <span className="text-lg">🎯</span>
        <h2 className="font-semibold text-gray-800">决策对照台</h2>
        <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">
          AI当镜子 · 对照你的判断 · 非投资建议
        </span>
      </div>

      {/* 客观风险/收益预估 */}
      <div className="px-6 pb-4">
        <div className="text-sm font-medium text-gray-600 mb-2">📐 风险 / 收益预估（客观算法）</div>
        {snapLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />)}
          </div>
        ) : hasRR ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                <div className="text-xs text-gray-500">现价</div>
                <div className="text-sm font-semibold text-gray-800">{fmt(rr!.price)}</div>
              </div>
              <div className="bg-green-50 rounded-lg px-3 py-2 border border-green-100">
                <div className="text-xs text-gray-500">参考止损位</div>
                <div className="text-sm font-semibold text-green-700">{fmt(rr!.stop_loss)}</div>
                <div className="text-[11px] text-green-600">下行 {fmt(rr!.risk_pct, '%')}</div>
              </div>
              <div className="bg-red-50 rounded-lg px-3 py-2 border border-red-100">
                <div className="text-xs text-gray-500">参考目标位</div>
                <div className="text-sm font-semibold text-red-600">{fmt(rr!.target)}</div>
                <div className="text-[11px] text-red-500">上行 {fmt(rr!.reward_pct, '%')}</div>
              </div>
              <div className="bg-indigo-50 rounded-lg px-3 py-2 border border-indigo-100">
                <div className="text-xs text-gray-500">盈亏比（赔率）</div>
                <div className="text-sm font-semibold text-indigo-700">{fmt(rr!.risk_reward_ratio)}</div>
                <div className="text-[11px] text-indigo-500">波动率 {fmt(rr!.volatility_20d, '%')}</div>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              {rr!.rr_label} · 支撑(近20日低) {fmt(rr!.support_20d)} / 压力(近60日高) {fmt(rr!.resistance_60d)}
              <span className="text-gray-400"> ｜ 止损=max(20日低, 现价−2ATR)，目标=60日高，均为客观参考非建议</span>
            </p>
          </>
        ) : (
          <p className="text-sm text-gray-400">风险收益数据暂时不可用（行情接口可能限频，请稍后刷新）</p>
        )}
      </div>

      {/* 用户预期输入 */}
      <div className="px-6 pb-4 border-t border-gray-100 pt-4">
        <div className="text-sm font-medium text-gray-600 mb-3">🧠 先填你自己的判断，再看 AI 是否和你一致</div>
        <div className="flex flex-wrap gap-6">
          <div>
            <div className="text-xs text-gray-500 mb-1.5">你的方向</div>
            <div className="flex gap-1.5">
              {(['bullish', 'bearish', 'unsure'] as Direction[]).map((d) => (
                <button
                  key={d}
                  onClick={() => setDirection(d)}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                    direction === d
                      ? d === 'bullish' ? 'bg-red-500 text-white border-red-500'
                        : d === 'bearish' ? 'bg-green-600 text-white border-green-600'
                        : 'bg-gray-500 text-white border-gray-500'
                      : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {DIR_LABEL[d]}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1.5">你的周期</div>
            <div className="flex gap-1.5">
              {(['long', 'short', 'unsure'] as Horizon[]).map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                    horizon === h ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {HOR_LABEL[h]}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-end">
            <button
              onClick={handleCompare}
              disabled={aiLoading}
              className="px-5 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700
                         disabled:opacity-50 transition-colors font-medium"
            >
              {aiLoading ? '⏳ AI 对照中...' : '🔍 对照 AI 判断'}
            </button>
          </div>
        </div>
      </div>

      {/* AI 对照结果 */}
      {aiLoading && (
        <div className="px-6 pb-5">
          <div className="h-4 bg-gray-100 rounded w-3/4 animate-pulse mb-2" />
          <div className="h-4 bg-gray-100 rounded w-1/2 animate-pulse" />
        </div>
      )}

      {decision && !aiLoading && (
        <div className="px-6 pb-5 space-y-4 border-t border-gray-100 pt-4">
          {/* 一致性高亮 */}
          {(() => {
            const cs = consistencyStyle(decision.consistency)
            return (
              <div className={`rounded-lg px-4 py-3 border ${cs.cls}`}>
                <div className="flex items-center flex-wrap gap-2 text-sm font-semibold">
                  <span>{cs.icon} 与你的预期：{decision.consistency}</span>
                  <span className="text-xs font-normal opacity-80">
                    你：{DIR_LABEL[direction]} / {HOR_LABEL[horizon]}　vs　
                    AI：{decision.ai_direction} / {decision.ai_horizon}（置信度 {decision.confidence}）
                  </span>
                </div>
                {decision.divergence && (
                  <p className="text-xs mt-1.5 opacity-90 font-normal leading-relaxed">{decision.divergence}</p>
                )}
              </div>
            )
          })()}

          {/* 长短线倾向 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
              <h3 className="text-sm font-medium text-blue-700 mb-2">
                📅 AI 倾向：{decision.ai_horizon}
              </h3>
              <p className="text-sm text-blue-900 leading-relaxed">{decision.horizon_reason}</p>
            </div>
            <div className="bg-amber-50 rounded-lg p-4 border border-amber-100">
              <h3 className="text-sm font-medium text-amber-700 mb-2">📐 赔率解读</h3>
              <p className="text-sm text-amber-900 leading-relaxed">{decision.risk_reward_comment || '—'}</p>
            </div>
          </div>

          {/* 关键因素 / 盲点 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
              <h3 className="text-sm font-medium text-gray-700 mb-2">🔑 关键因素</h3>
              <ul className="space-y-1.5">
                {decision.key_factors.length > 0 ? decision.key_factors.map((f, i) => (
                  <li key={i} className="text-sm text-gray-700 flex gap-2">
                    <span className="text-gray-400 mt-0.5">•</span><span>{f}</span>
                  </li>
                )) : <li className="text-sm text-gray-400 italic">—</li>}
              </ul>
            </div>
            <div className="bg-orange-50 rounded-lg p-4 border border-orange-100">
              <h3 className="text-sm font-medium text-orange-700 mb-2">👁️ 容易忽略的盲点</h3>
              <ul className="space-y-1.5">
                {decision.blind_spots.length > 0 ? decision.blind_spots.map((b, i) => (
                  <li key={i} className="text-sm text-orange-800 flex gap-2">
                    <span className="text-orange-400 mt-0.5">•</span><span>{b}</span>
                  </li>
                )) : <li className="text-sm text-orange-600 italic">—</li>}
              </ul>
            </div>
          </div>

          <p className="text-xs text-gray-400">
            ※ AI 判断仅作为你独立思考的对照参照，不构成任何投资建议。最终决策请结合自身研究与风险承受能力。
          </p>
        </div>
      )}
    </div>
  )
}
