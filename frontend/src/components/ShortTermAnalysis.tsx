/**
 * AI 短线研判组件
 * 结合技术面 + 资金面，输出机会/风险（吸筹/承接/出货/炸板等短线视角）
 */
import type { ShortTermResult } from '../types/stock'

interface Props {
  result: ShortTermResult | null
  loading: boolean
  onGenerate: () => void
  generated: boolean
}

function ratingStyle(rating: string): string {
  if (rating.includes('多')) return 'bg-red-50 text-red-600 border-red-100'
  if (rating.includes('空')) return 'bg-green-50 text-green-700 border-green-100'
  return 'bg-gray-50 text-gray-600 border-gray-200'
}

export default function ShortTermAnalysis({ result, loading, onGenerate, generated }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-6 pt-5 pb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">⚡</span>
            <h2 className="font-semibold text-gray-800">AI 短线研判</h2>
            <span className="text-xs bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full">
              技术+资金 · 仅供参考，非投资建议
            </span>
          </div>
          {result && (
            <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${ratingStyle(result.rating)}`}>
              短期倾向：{result.rating}
            </span>
          )}
        </div>

        {/* 未生成时显示按钮 */}
        {!generated && !loading && (
          <button
            onClick={onGenerate}
            className="w-full py-3 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors"
          >
            生成 AI 短线研判（基于实时技术面与资金流）
          </button>
        )}

        {loading && (
          <div className="space-y-2 py-2">
            <div className="h-4 bg-gray-100 rounded w-full animate-pulse" />
            <div className="h-4 bg-gray-100 rounded w-4/5 animate-pulse" />
            <div className="text-xs text-gray-400 mt-2">AI 正在结合 K线、MACD、主力资金流研判…</div>
          </div>
        )}

        {result && !loading && (
          <p className="text-gray-800 leading-relaxed text-[15px]">{result.summary}</p>
        )}
      </div>

      {result && !loading && (
        <div className="px-6 pb-5 space-y-4">
          {/* 技术面 / 资金面解读 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {result.technical && (
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
                <h3 className="text-sm font-medium text-blue-700 mb-2">📊 技术面</h3>
                <p className="text-sm text-blue-900 leading-relaxed">{result.technical}</p>
              </div>
            )}
            {result.capital && (
              <div className="bg-purple-50 rounded-lg p-4 border border-purple-100">
                <h3 className="text-sm font-medium text-purple-700 mb-2">💰 资金面</h3>
                <p className="text-sm text-purple-900 leading-relaxed">{result.capital}</p>
              </div>
            )}
          </div>

          {/* 机会 / 风险 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-red-50 rounded-lg p-4 border border-red-100">
              <h3 className="text-sm font-medium text-red-700 mb-3 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-500" /> 机会
              </h3>
              <ul className="space-y-2">
                {result.opportunities.length > 0 ? result.opportunities.map((o, i) => (
                  <li key={i} className="text-sm text-red-800 leading-relaxed flex gap-2">
                    <span className="shrink-0 text-red-400 mt-0.5">•</span><span>{o}</span>
                  </li>
                )) : <li className="text-sm text-red-600 italic">现有数据未识别明确机会</li>}
              </ul>
            </div>
            <div className="bg-green-50 rounded-lg p-4 border border-green-100">
              <h3 className="text-sm font-medium text-green-700 mb-3 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-green-500" /> 风险
              </h3>
              <ul className="space-y-2">
                {result.risks.length > 0 ? result.risks.map((r, i) => (
                  <li key={i} className="text-sm text-green-800 leading-relaxed flex gap-2">
                    <span className="shrink-0 text-green-400 mt-0.5">•</span><span>{r}</span>
                  </li>
                )) : <li className="text-sm text-green-600 italic">现有数据未发现明显风险</li>}
              </ul>
            </div>
          </div>

          {/* 龙虎榜简评 */}
          {result.lhb_note && (
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
              <h3 className="text-sm font-medium text-gray-600 mb-2">🏆 龙虎榜 / 主力席位</h3>
              <p className="text-sm text-gray-700 leading-relaxed">{result.lhb_note}</p>
            </div>
          )}

          <p className="text-xs text-gray-400 pt-1">
            ※ 本研判基于日线级公开数据与 AI 推理，不构成任何投资建议。短线有风险，决策需谨慎。
          </p>
        </div>
      )}
    </div>
  )
}
