/**
 * AI 分析展示组件
 * 优化：更好的视觉层次、风险等级标识、展开动画
 */
import { useState } from 'react'
import type { QuickAnalysisResult } from '../types/stock'

interface Props {
  analysis: QuickAnalysisResult | null
  loading: boolean
}

export default function AIAnalysis({ analysis, loading }: Props) {
  const [expanded, setExpanded] = useState(true)

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-5 h-5 bg-gray-200 rounded animate-pulse" />
          <div className="h-5 bg-gray-200 rounded w-20 animate-pulse" />
        </div>
        <div className="space-y-2">
          <div className="h-4 bg-gray-100 rounded w-full animate-pulse" />
          <div className="h-4 bg-gray-100 rounded w-4/5 animate-pulse" />
          <div className="h-4 bg-gray-100 rounded w-3/5 animate-pulse" />
        </div>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 text-gray-400">
          <span className="text-lg">🤖</span>
          <span className="text-sm">AI 分析尚未生成（请确认 API Key 已配置）</span>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* 头部 */}
      <div className="px-6 pt-5 pb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">🤖</span>
            <h2 className="font-semibold text-gray-800">AI 快速分析</h2>
            <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
              AI 生成 · 仅供参考
            </span>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            {expanded ? '收起' : '展开'}
          </button>
        </div>

        {/* 一句话总结 — 始终可见 */}
        <p className="text-gray-800 leading-relaxed text-[15px]">{analysis.summary}</p>
      </div>

      {/* 详细分析 — 可折叠 */}
      {expanded && (
        <div className="px-6 pb-5 space-y-4">
          {/* 亮点 + 风险 双栏 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 亮点 */}
            <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-100">
              <h3 className="text-sm font-medium text-emerald-700 mb-3 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                亮点
              </h3>
              <ul className="space-y-2">
                {analysis.strengths.length > 0 ? (
                  analysis.strengths.map((s, i) => (
                    <li key={i} className="text-sm text-emerald-800 leading-relaxed flex gap-2">
                      <span className="shrink-0 text-emerald-400 mt-0.5">•</span>
                      <span>{s}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-emerald-600 italic">
                    现有数据不足以识别明确亮点
                  </li>
                )}
              </ul>
            </div>

            {/* 风险 */}
            <div className="bg-red-50 rounded-lg p-4 border border-red-100">
              <h3 className="text-sm font-medium text-red-700 mb-3 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                风险提示
              </h3>
              <ul className="space-y-2">
                {analysis.risks.length > 0 ? (
                  analysis.risks.map((r, i) => (
                    <li key={i} className="text-sm text-red-800 leading-relaxed flex gap-2">
                      <span className="shrink-0 text-red-400 mt-0.5">•</span>
                      <span>{r}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-sm text-red-600 italic">
                    现有数据未发现明显风险信号
                  </li>
                )}
              </ul>
            </div>
          </div>

          {/* 指标解读 */}
          {analysis.metrics_commentary && (
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
              <h3 className="text-sm font-medium text-gray-600 mb-2 flex items-center gap-1.5">
                <span className="text-sm">📊</span>
                指标解读
              </h3>
              <p className="text-sm text-gray-700 leading-relaxed">
                {analysis.metrics_commentary}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
