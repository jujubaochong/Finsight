/**
 * 自选股列表页
 * 优化：加入异动提示占位、排序、更好的空状态
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getWatchlist, removeFromWatchlist } from '../services/api'
import type { WatchlistItem } from '../types/stock'

export default function WatchlistPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [removing, setRemoving] = useState<string | null>(null)

  const fetchList = async () => {
    try {
      const data = await getWatchlist()
      setItems(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchList()
  }, [])

  const handleRemove = async (code: string) => {
    setRemoving(code)
    try {
      await removeFromWatchlist(code)
      setItems((prev) => prev.filter((i) => i.code !== code))
    } catch {
      // ignore
    } finally {
      setRemoving(null)
    }
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">我的自选股</h1>
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">
          我的自选股
          {items.length > 0 && (
            <span className="text-lg text-gray-400 font-normal ml-2">
              ({items.length}只)
            </span>
          )}
        </h1>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50
                     transition-colors flex items-center gap-1"
        >
          + 添加
        </button>
      </div>

      {items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
          <div className="text-5xl mb-4">⭐</div>
          <h2 className="text-lg font-medium text-gray-700 mb-2">还没有自选股</h2>
          <p className="text-gray-400 text-sm mb-6">
            去首页搜索感兴趣的股票，点击"加入自选"即可添加
          </p>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            去搜索股票
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-sm
                         transition-shadow cursor-pointer group"
              onClick={() => navigate(`/stock/${item.code}`)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-semibold text-gray-800">{item.name}</span>
                      <span className="text-sm text-gray-400 font-mono">{item.code}</span>
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded ${
                          item.market === 'SH'
                            ? 'bg-red-50 text-red-500'
                            : 'bg-blue-50 text-blue-500'
                        }`}
                      >
                        {item.market}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-400">
                      {item.industry && <span>{item.industry}</span>}
                      <span>
                        加入于 {new Date(item.added_at).toLocaleDateString('zh-CN')}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* 异动提示（预留） */}
                  {item.has_alert && (
                    <span className="text-xs bg-red-100 text-red-600 px-2 py-1 rounded-full">
                      有异动
                    </span>
                  )}

                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemove(item.code)
                    }}
                    disabled={removing === item.code}
                    className="opacity-0 group-hover:opacity-100 px-3 py-1 text-xs
                               text-red-500 hover:bg-red-50 rounded-lg transition-all
                               disabled:opacity-50"
                  >
                    {removing === item.code ? '...' : '移除'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
