/**
 * 报告查看页
 * 优化：细化进度展示、更好的大纲交互、打印支持
 */
import { useState, useEffect } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { getReportStatus, getReport } from '../services/api'
import type { ReportInfo } from '../types/stock'

const PROGRESS_STEPS = [
  { key: 'data_fetch', label: '获取数据', icon: '📊' },
  { key: 'ai_analysis', label: '分析财务', icon: '🔍' },
  { key: 'ai_writing', label: '撰写报告', icon: '✍️' },
  { key: 'saving', label: '保存报告', icon: '💾' },
]

export default function ReportPage() {
  const { code } = useParams<{ code: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const taskId = searchParams.get('task')

  const [report, setReport] = useState<ReportInfo | null>(null)
  const [status, setStatus] = useState<string>('loading')
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('正在准备数据...')
  const [error, setError] = useState<string | null>(null)
  const [activeSection, setActiveSection] = useState('')

  // 轮询报告状态
  useEffect(() => {
    if (!taskId) {
      setError('缺少任务ID')
      return
    }

    let cancelled = false

    const poll = async () => {
      if (cancelled) return
      try {
        const s = await getReportStatus(taskId)
        if (cancelled) return

        setStatus(s.status)
        setProgress(s.progress)
        setMessage(s.message)

        if (s.status === 'completed') {
          const r = await getReport(parseInt(taskId))
          if (!cancelled) setReport(r)
        } else if (s.status === 'failed') {
          setError(s.message || '报告生成失败')
        } else {
          setTimeout(poll, 2000)
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || '获取报告状态失败')
      }
    }

    poll()
    return () => { cancelled = true }
  }, [taskId])

  // 提取报告章节标题
  const sections = report?.content
    ? report.content
        .split('\n')
        .filter((line) => line.startsWith('## '))
        .map((line) => line.replace('## ', '').trim())
    : []

  // 滚动高亮当前章节
  useEffect(() => {
    if (!report) return
    const handleScroll = () => {
      const headings = document.querySelectorAll('.report-content h2')
      let current = ''
      headings.forEach((h) => {
        const rect = h.getBoundingClientRect()
        if (rect.top <= 120) current = h.textContent?.trim() || ''
      })
      setActiveSection(current)
    }
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [report])

  return (
    <div>
      {/* 返回按钮 */}
      <button
        onClick={() => navigate(`/stock/${code}`)}
        className="text-sm text-gray-500 hover:text-blue-600 mb-4 inline-flex items-center gap-1"
      >
        ← 返回 {code} 详情
      </button>

      {/* 生成中状态 */}
      {status === 'processing' && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <div className="text-4xl mb-4">📝</div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">报告正在生成中</h2>
          <p className="text-gray-500 mb-8">{message}</p>

          {/* 步骤进度 */}
          <div className="flex items-center justify-center gap-2 mb-8 max-w-md mx-auto">
            {PROGRESS_STEPS.map((step, i) => {
              const isActive = progress >= (i + 1) * 25 - 10
              const isDone = progress >= (i + 1) * 25
              return (
                <div key={step.key} className="flex items-center gap-2">
                  <div
                    className={`flex flex-col items-center ${
                      isActive ? 'opacity-100' : 'opacity-40'
                    }`}
                  >
                    <span className="text-lg">{step.icon}</span>
                    <span className="text-xs text-gray-500 mt-1">{step.label}</span>
                  </div>
                  {i < PROGRESS_STEPS.length - 1 && (
                    <div
                      className={`w-8 h-0.5 ${isDone ? 'bg-blue-500' : 'bg-gray-200'}`}
                    />
                  )}
                </div>
              )
            })}
          </div>

          {/* 进度条 */}
          <div className="w-72 mx-auto bg-gray-200 rounded-full h-2 mb-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-gray-400">
            预计需要 30-60 秒，生成完成后自动展示
          </p>
        </div>
      )}

      {/* 加载中（初始状态） */}
      {status === 'loading' && !error && (
        <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
          <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">加载中...</p>
        </div>
      )}

      {/* 失败状态 */}
      {error && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <div className="text-4xl mb-4">❌</div>
          <h2 className="text-lg font-medium text-gray-800 mb-2">报告生成失败</h2>
          <p className="text-gray-500 mb-6 text-sm">{error}</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => navigate(`/stock/${code}`)}
              className="px-5 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
            >
              返回详情页
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
            >
              重试
            </button>
          </div>
        </div>
      )}

      {/* 报告内容 */}
      {report && (
        <div className="flex gap-6">
          {/* 左侧大纲 */}
          {sections.length > 0 && (
            <aside className="hidden lg:block w-52 shrink-0">
              <div className="sticky top-20 bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-xs font-medium text-gray-400 uppercase mb-3 tracking-wider">
                  报告大纲
                </h3>
                <nav className="space-y-0.5">
                  {sections.map((s) => (
                    <a
                      key={s}
                      href={`#${s}`}
                      className={`block text-sm py-1.5 px-2 rounded transition-colors leading-snug ${
                        activeSection === s
                          ? 'bg-blue-50 text-blue-700 font-medium'
                          : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
                      }`}
                    >
                      {s}
                    </a>
                  ))}
                </nav>
              </div>
            </aside>
          )}

          {/* 右侧正文 */}
          <div className="flex-1 min-w-0">
            <div className="bg-white rounded-xl border border-gray-200 p-8">
              <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-bold text-gray-800">{report.title}</h1>
                <span className="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded-full">
                  AI 生成
                </span>
              </div>

              <div className="report-content prose prose-sm max-w-none prose-headings:scroll-mt-20">
                <ReactMarkdown
                  components={{
                    h2: ({ children, ...props }) => (
                      <h2 id={String(children)} className="text-lg font-bold text-gray-800 mt-8 mb-4 pb-2 border-b border-gray-100" {...props}>
                        {children}
                      </h2>
                    ),
                    h3: ({ children, ...props }) => (
                      <h3 className="text-base font-semibold text-gray-700 mt-6 mb-3" {...props}>
                        {children}
                      </h3>
                    ),
                    p: ({ children, ...props }) => (
                      <p className="text-gray-700 leading-relaxed mb-3" {...props}>
                        {children}
                      </p>
                    ),
                    li: ({ children, ...props }) => (
                      <li className="text-gray-700 leading-relaxed" {...props}>
                        {children}
                      </li>
                    ),
                    strong: ({ children, ...props }) => (
                      <strong className="text-gray-900" {...props}>{children}</strong>
                    ),
                  }}
                >
                  {report.content}
                </ReactMarkdown>
              </div>

              {/* 报告元信息 */}
              <div className="mt-8 pt-4 border-t border-gray-100 text-xs text-gray-400 space-y-1">
                <p>⚠️ 本报告由 FinSight AI 自动生成，内容仅供参考，不构成投资建议。</p>
                <p>📅 生成时间：{new Date(report.created_at).toLocaleString('zh-CN')}</p>
                <p>📊 数据来源：公开财务报告、上市公司公告</p>
              </div>
            </div>

            {/* 底部操作 */}
            <div className="flex justify-center gap-3 mt-6 pb-8">
              <button
                onClick={() => {
                  const blob = new Blob([report.content], { type: 'text/markdown' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `${report.title}.md`
                  a.click()
                  URL.revokeObjectURL(url)
                }}
                className="px-5 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50
                           flex items-center gap-2"
              >
                📄 下载 Markdown
              </button>
              <button
                onClick={() => window.print()}
                className="px-5 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50
                           flex items-center gap-2"
              >
                🖨️ 打印
              </button>
              <button
                onClick={() => navigate(`/stock/${code}`)}
                className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
              >
                返回详情页
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
