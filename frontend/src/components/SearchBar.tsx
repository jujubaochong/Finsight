/**
 * 搜索栏组件 — 带实时下拉建议
 * 实现文档中描述的 debounce 300ms + 下拉建议 + 键盘导航
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchStocks } from '../services/api'
import { useDebounce } from '../hooks/useDebounce'
import type { StockBrief } from '../types/stock'

interface Props {
  autoFocus?: boolean
  size?: 'normal' | 'large'
  placeholder?: string
}

export default function SearchBar({
  autoFocus = false,
  size = 'normal',
  placeholder = '输入股票代码或名称，如 平安银行 / 000001',
}: Props) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<StockBrief[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const debouncedQuery = useDebounce(query, 300)

  // 搜索建议
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.trim().length === 0) {
      setSuggestions([])
      setShowDropdown(false)
      return
    }

    const fetchSuggestions = async () => {
      setLoading(true)
      try {
        const res = await searchStocks(debouncedQuery)
        setSuggestions(res.results.slice(0, 6))
        setShowDropdown(res.results.length > 0)
        setActiveIndex(-1)
      } catch {
        setSuggestions([])
      } finally {
        setLoading(false)
      }
    }

    fetchSuggestions()
  }, [debouncedQuery])

  // 键盘导航
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!showDropdown || suggestions.length === 0) {
        if (e.key === 'Enter' && query.trim()) {
          // 直接搜索跳转
          navigate(`/stock/${query.trim()}`)
        }
        return
      }

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault()
          setActiveIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0))
          break
        case 'ArrowUp':
          e.preventDefault()
          setActiveIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1))
          break
        case 'Enter':
          e.preventDefault()
          if (activeIndex >= 0 && activeIndex < suggestions.length) {
            handleSelect(suggestions[activeIndex])
          } else if (suggestions.length === 1) {
            handleSelect(suggestions[0])
          } else if (query.trim()) {
            navigate(`/stock/${query.trim()}`)
          }
          break
        case 'Escape':
          setShowDropdown(false)
          setActiveIndex(-1)
          break
      }
    },
    [showDropdown, suggestions, activeIndex, query, navigate]
  )

  const handleSelect = (stock: StockBrief) => {
    setShowDropdown(false)
    setQuery('')
    // 保存到最近浏览
    saveRecentSearch(stock)
    navigate(`/stock/${stock.code}`)
  }

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const inputClasses =
    size === 'large'
      ? 'w-full px-5 py-4 rounded-xl border border-gray-300 text-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm'
      : 'w-full px-4 py-2.5 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'

  return (
    <div className="relative w-full">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
          placeholder={placeholder}
          className={inputClasses}
          autoFocus={autoFocus}
          autoComplete="off"
        />
        {/* 搜索图标 / loading */}
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          {loading ? (
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          )}
        </div>
      </div>

      {/* 下拉建议 */}
      {showDropdown && suggestions.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-white rounded-lg border border-gray-200 shadow-lg overflow-hidden"
        >
          {suggestions.map((s, i) => (
            <button
              key={s.code}
              onClick={() => handleSelect(s)}
              className={`w-full px-4 py-3 text-left flex items-center gap-3 transition-colors ${
                i === activeIndex ? 'bg-blue-50' : 'hover:bg-gray-50'
              }`}
            >
              <span className="font-mono text-sm text-gray-600 w-16">{s.code}</span>
              <span className="font-medium text-gray-800">{s.name}</span>
              <span
                className={`text-xs px-1.5 py-0.5 rounded ${
                  s.market === 'SH'
                    ? 'bg-red-100 text-red-600'
                    : s.market === 'BJ'
                    ? 'bg-orange-100 text-orange-600'
                    : 'bg-blue-100 text-blue-600'
                }`}
              >
                {s.market}
              </span>
              {s.industry && (
                <span className="text-xs text-gray-400 ml-auto">{s.industry}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ====== 最近浏览记录 ======

const RECENT_KEY = 'finsight_recent_searches'
const MAX_RECENT = 5

function saveRecentSearch(stock: StockBrief) {
  try {
    const stored = localStorage.getItem(RECENT_KEY)
    let recent: StockBrief[] = stored ? JSON.parse(stored) : []
    // 移除已有的同一只股票
    recent = recent.filter((s) => s.code !== stock.code)
    // 放到最前面
    recent.unshift(stock)
    // 最多保留 5 条
    recent = recent.slice(0, MAX_RECENT)
    localStorage.setItem(RECENT_KEY, JSON.stringify(recent))
  } catch {
    // localStorage 不可用时静默失败
  }
}

export function getRecentSearches(): StockBrief[] {
  try {
    const stored = localStorage.getItem(RECENT_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}
