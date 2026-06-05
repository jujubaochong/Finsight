/**
 * 异动监控页面
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAlerts, scanAlerts, markAlertRead, markAllAlertsRead } from '../services/api'
import type { AlertItem } from '../types/stock'

const SEVERITY_CONFIG = {
  high: { label: '高', color: 'bg-red-100 text-red-700', dot: 'bg-red-500' },
  medium: { label: '中', color: 'bg-yellow-100 text-yellow-700', dot: 'bg-yellow-500' },
  low: { label: '低', color: 'bg-gray-100 text-gray-600', dot: 'bg-gray-400' },
}

const TYPE_CONFIG: Record<string, { label: string; icon: string }> = {
  announcement: { label: '公告', icon: '📋' },
  shareholder: { label: '股东', icon: '👤' },
  regulatory: { label: '监管', icon: '⚠️' },
  financial: { label: '财务', icon: '📊' },
}

export default function AlertsPage() {
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [filter, setFilter] = useState<'all' | 'unread'>('all')

  const fetchAlerts = async () => {
    try {
      const data = await getAlerts(filter === 'unread')
      setAlerts(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAlerts()
  }, [filter])

  const handleScan = async () => {
    setScanning(true)
    try {
      const result = await scanAlerts()
      if (result.new_alerts > 0) {
        await fetchAlerts()
      }
    } catch {
      // ignore
    } finally {
      setScanning(false)
    }
  }

  const handleMarkRead = async (id: number) => {
    await markAlertRead(id)
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)))
  }

  const handleMarkAllRead = async () => {
    await markAllAlertsRead()
    setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })))
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">异动监控</h1>
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  const unreadCount = alerts.filter((a) => !a.is_read).length

  return (
    <div>
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">
            异动监控
            {unreadCount > 0 && (
              <span className="ml-2 text-sm bg-red-500 text-white px-2 py-0.5 rounded-full font-normal">
                {unreadCount}
              </span>
            )}
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            自动监测自选股的重大公告、股东变动、监管事件和财务异常
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700
                       disabled:opacity-50 transition-colors"
          >
            {scanning ? '扫描中...' : '🔍 立即扫描'}
          </button>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              全部已读
            </button>
          )}
        </div>
      </div>

      {/* 过滤 */}
      <div className="flex gap-2 mb-4">
        {(['all', 'unread'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f === 'all' ? '全部' : '未读'}
          </button>
        ))}
      </div>

      {/* 异动列表 */}
      {alerts.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
          <div className="text-5xl mb-4">🔔</div>
          <h2 className="text-lg font-medium text-gray-700 mb-2">
            {filter === 'unread' ? '没有未读异动' : '暂无异动记录'}
          </h2>
          <p className="text-gray-400 text-sm mb-6">
            添加自选股后，系统会自动监测重要变化
          </p>
          <button
            onClick={handleScan}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            手动扫描一次
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => {
            const severity = SEVERITY_CONFIG[alert.severity]
            const type = TYPE_CONFIG[alert.alert_type] || { label: '其他', icon: '📌' }

            return (
              <div
                key={alert.id}
                className={`bg-white rounded-xl border p-4 transition-all cursor-pointer hover:shadow-sm ${
                  alert.is_read ? 'border-gray-100 opacity-70' : 'border-gray-200'
                }`}
                onClick={() => navigate(`/stock/${alert.stock_code}`)}
              >
                <div className="flex items-start gap-3">
                  {/* 未读标记 */}
                  {!alert.is_read && (
                    <span className={`w-2 h-2 rounded-full mt-2 shrink-0 ${severity.dot}`} />
                  )}
                  {alert.is_read && <span className="w-2 shrink-0" />}

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-sm">{type.icon}</span>
                      <span className="font-medium text-gray-800 text-sm">{alert.title}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${severity.color}`}>
                        {severity.label}
                      </span>
                      <span className="text-xs text-gray-400 ml-auto">
                        {new Date(alert.detected_at).toLocaleDateString('zh-CN')}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 truncate">{alert.description}</p>
                  </div>

                  {/* 标记已读 */}
                  {!alert.is_read && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleMarkRead(alert.id)
                      }}
                      className="text-xs text-gray-400 hover:text-blue-600 shrink-0 px-2 py-1"
                    >
                      已读
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
