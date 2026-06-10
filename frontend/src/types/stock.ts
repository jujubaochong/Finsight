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
  source?: 'ai' | 'rule_engine'
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
  pending?: boolean
  message?: string
}
