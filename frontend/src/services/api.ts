/**
 * API 请求封装
 */
import axios from 'axios'
import type {
  StockDetail, SearchResponse, QuickAnalysisResult, ReportInfo,
  WatchlistItem, AlertItem, IndustryComparison,
} from '../types/stock'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// ====== 股票相关 ======

export async function searchStocks(query: string): Promise<SearchResponse> {
  const { data } = await api.get('/stocks/search', { params: { q: query } })
  return data
}

export async function getStockDetail(code: string): Promise<StockDetail> {
  const { data } = await api.get(`/stocks/${code}`)
  return data
}

export async function refreshStockData(code: string): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post(`/stocks/${code}/refresh`)
  return data
}

// ====== AI 分析相关 ======

export async function quickAnalysis(code: string): Promise<{ code: string; analysis: QuickAnalysisResult }> {
  const { data } = await api.post(`/analysis/quick/${code}`)
  return data
}

export async function deepAnalysis(code: string, focus: string = 'full'): Promise<{ code: string; task_id: string }> {
  const { data } = await api.post(`/analysis/deep/${code}`, null, { params: { focus } })
  return data
}

// ====== 报告相关 ======

export async function generateReport(code: string, template: string = 'standard'): Promise<{ code: string; task_id: string }> {
  const { data } = await api.post(`/reports/generate/${code}`, { template })
  return data
}

export async function getReportStatus(taskId: string): Promise<{ task_id: string; status: string; progress: number; message: string }> {
  const { data } = await api.get(`/reports/status/${taskId}`)
  return data
}

export async function getReport(reportId: number): Promise<ReportInfo> {
  const { data } = await api.get(`/reports/${reportId}`)
  return data
}

// ====== 自选股相关 ======

export async function getWatchlist(): Promise<WatchlistItem[]> {
  const { data } = await api.get('/stocks/watchlist/list')
  return data
}

export async function addToWatchlist(code: string): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post('/stocks/watchlist/add', { code })
  return data
}

export async function removeFromWatchlist(code: string): Promise<{ success: boolean }> {
  const { data } = await api.delete(`/stocks/watchlist/${code}`)
  return data
}

// ====== 异动监控 ======

export async function getAlerts(unreadOnly: boolean = false): Promise<AlertItem[]> {
  const { data } = await api.get('/alerts/list', { params: { unread_only: unreadOnly } })
  return data
}

export async function scanAlerts(): Promise<{ success: boolean; new_alerts: number }> {
  const { data } = await api.post('/alerts/scan')
  return data
}

export async function markAlertRead(alertId: number): Promise<{ success: boolean }> {
  const { data } = await api.post(`/alerts/read/${alertId}`)
  return data
}

export async function markAllAlertsRead(): Promise<{ success: boolean }> {
  const { data } = await api.post('/alerts/read-all')
  return data
}

export async function getUnreadAlertCount(): Promise<{ unread_count: number }> {
  const { data } = await api.get('/alerts/count')
  return data
}

// ====== 行业对标 ======

export async function getIndustryComparison(code: string): Promise<IndustryComparison> {
  const { data } = await api.get(`/industry/comparison/${code}`)
  return data
}

export async function getIndustryPeers(code: string): Promise<{ code: string; peers: any[]; count: number }> {
  const { data } = await api.get(`/industry/peers/${code}`)
  return data
}

export default api
