/**
 * 全局布局组件
 */
import { useState, useEffect } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { getUnreadAlertCount } from '../services/api'

export default function Layout() {
  const [unreadCount, setUnreadCount] = useState(0)

  // 定期检查未读异动数
  useEffect(() => {
    const fetchCount = () => {
      getUnreadAlertCount()
        .then((res) => setUnreadCount(res.unread_count))
        .catch(() => {})
    }
    fetchCount()
    const interval = setInterval(fetchCount, 60000) // 每分钟检查
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航 */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <NavLink to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <span className="text-xl font-bold">
              <span className="text-blue-600">Fin</span>
              <span className="text-gray-800">Sight</span>
            </span>
            <span className="text-xs text-gray-400 hidden sm:inline">AI 投研助手</span>
          </NavLink>

          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                }`
              }
              end
            >
              搜索
            </NavLink>
            <NavLink
              to="/watchlist"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                }`
              }
            >
              自选股
            </NavLink>
            <NavLink
              to="/alerts"
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-lg text-sm transition-colors relative ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                }`
              }
            >
              异动
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white
                                 text-[10px] flex items-center justify-center rounded-full">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </NavLink>
          </nav>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        <Outlet />
      </main>

      {/* 底部 */}
      <footer className="border-t border-gray-100 py-6 mt-8">
        <div className="max-w-6xl mx-auto px-4 text-center text-xs text-gray-400">
          <p>FinSight — AI 驱动的智能投研助手 · 数据仅供参考，不构成投资建议</p>
          <p className="mt-1">数据来源：AkShare（公开数据） · AI：DeepSeek</p>
        </div>
      </footer>
    </div>
  )
}
