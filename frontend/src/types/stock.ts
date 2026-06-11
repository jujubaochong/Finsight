/**
 * 股票相关类型定义
 */

export interface StockBrief {
  code: string
  name: string
  market: 'SZ' | 'SH' | 'BJ'
  industry?: string
}

export interface FinancialItem {
  report_period: string
  revenue: number | null
  net_profit: number | null
  total_assets: number | null
  total_equity: number | null
  operating_cash_flow: number | null
  receivables: number | null
  inventory: number | null
  eps: number | null
  pe_ratio: number | null
  pb_ratio: number | null
  gross_margin: number | null
  net_margin: number | null
  roe: number | null
  debt_ratio: number | null
  revenue_growth_yoy: number | null
  profit_growth_yoy: number | null
}

export interface AnnouncementItem {
  id: number
  title: string
  publish_date: string
  summary: string | null
  url: string | null
}

export interface QuickAnalysisResult {
  summary: string
  strengths: string[]
  risks: string[]
  metrics_commentary: string
}

export interface StockDetail {
  code: string
  name: string
  market: string
  industry: string | null
  listing_date: string | null
  is_active: boolean
  financials: FinancialItem[]
  announcements: AnnouncementItem[]
  quick_analysis: QuickAnalysisResult | null
}

export interface ReportInfo {
  report_id: number
  title: string
  content: string
  report_type: string
  status: string
  created_at: string
}

export interface WatchlistItem {
  id: number
  code: string
  name: string
  market: string
  industry: string | null
  added_at: string
  quick_summary: string | null
  has_alert: boolean
}

export interface SearchResponse {
  query: string
  results: StockBrief[]
}

// ====== 异动监控 ======

export interface AlertItem {
  id: number
  stock_code: string
  stock_name: string
  alert_type: 'announcement' | 'shareholder' | 'regulatory' | 'financial'
  severity: 'high' | 'medium' | 'low'
  title: string
  description: string
  is_read: boolean
  detected_at: string
}

// ====== 行业对标 ======

export interface IndustryStats {
  avg: number
  median: number
  max: number
  min: number
  count: number
}

export interface IndustryRanking {
  rank: number
  total: number
  percentile: number
}

export interface IndustryPeer {
  code: string
  name: string
  report_period?: string
  revenue?: number | null
  net_profit?: number | null
  net_margin?: number | null
  roe?: number | null
  debt_ratio?: number | null
  revenue_growth_yoy?: number | null
  profit_growth_yoy?: number | null
}

export interface IndustryComparison {
  code: string
  name: string
  industry: string
  target_metrics: {
    report_period: string
    revenue: number | null
    net_profit: number | null
    net_margin: number | null
    roe: number | null
    debt_ratio: number | null
    revenue_growth_yoy: number | null
    profit_growth_yoy: number | null
  }
  industry_stats: Record<string, IndustryStats>
  rankings: Record<string, IndustryRanking>
  peer_count: number
  top_peers: IndustryPeer[]
  error?: string
}


// ====== 行情 / 技术面 / 资金面 ======

export interface MarketSnapshot {
  code: string
  latest: {
    date: string | null
    close: number | null
    pct_chg: number | null
    turnover: number | null
    chg_5d: number | null
  }
  indicators: {
    ma5?: number | null
    ma10?: number | null
    ma20?: number | null
    ma60?: number | null
    macd_dif?: number | null
    macd_dea?: number | null
    macd?: number | null
    macd_cross?: 'golden' | 'dead' | 'none'
    kdj_k?: number | null
    kdj_d?: number | null
    kdj_j?: number | null
    rsi?: number | null
    series?: { date: string; close: number; dif: number; dea: number; macd: number }[]
  }
  fund_flow: {
    signal?: 'accumulate' | 'distribute' | 'neutral'
    label?: string
    main_net_5d?: number
    main_net_today?: number
    main_net_pct_today?: number | null
    positive_days_5d?: number
    series?: { date: string; main_net: number; pct_chg: number | null }[]
  }
  lhb: {
    date: string
    reason: string
    interpret: string
    net_buy: number | null
    pct_chg: number | null
    after_1d: number | null
    after_5d: number | null
  }[]
}

export interface ShortTermResult {
  rating: string
  summary: string
  technical: string
  capital: string
  opportunities: string[]
  risks: string[]
  lhb_note: string
}
