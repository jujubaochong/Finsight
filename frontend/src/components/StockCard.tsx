/**
 * 股票卡片组件 — 搜索结果 / 自选列表用
 */
import { useNavigate } from 'react-router-dom'
import type { StockBrief } from '../types/stock'

interface Props {
  stock: StockBrief
  extra?: React.ReactNode
}

export default function StockCard({ stock, extra }: Props) {
  const navigate = useNavigate()

  return (
    <div
      onClick={() => navigate(`/stock/${stock.code}`)}
      className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md hover:border-blue-300
                 transition-all cursor-pointer"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-gray-800">{stock.name}</span>
          <span className="text-sm text-gray-500">{stock.code}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${
            stock.market === 'SH' ? 'bg-red-100 text-red-600' : stock.market === 'SZ' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'
          }`}>
            {stock.market === 'SH' ? '沪市' : stock.market === 'SZ' ? '深市' : '北交所'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {stock.industry && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
              {stock.industry}
            </span>
          )}
          {extra}
        </div>
      </div>
    </div>
  )
}
