/**
 * 股票详情数据 Hook
 */
import { useState, useEffect, useCallback } from 'react'
import { getStockDetail } from '../services/api'
import type { StockDetail } from '../types/stock'

export function useStockData(code: string | undefined) {
  const [data, setData] = useState<StockDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!code) return
    setLoading(true)
    setError(null)
    try {
      const result = await getStockDetail(code)
      setData(result)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [code])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}
