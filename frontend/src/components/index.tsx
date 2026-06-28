// Reusable components

import React from 'react'

// ── Source Badge ───────────────────────────────────────────────────────────────
export const SourceBadge = ({ source }: { source: string }) => {
  const styles: Record<string, string> = {
    regex:             'bg-green-100 text-green-800 border border-green-300',
    llm:               'bg-yellow-100 text-yellow-800 border border-yellow-300',
    auditor_verified:  'bg-blue-100 text-blue-800 border border-blue-300',
  }
  const labels: Record<string, string> = {
    regex:            '✅ regex',
    llm:              '⚠️ LLM',
    auditor_verified: '🔒 verified',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[source] ?? 'bg-gray-100 text-gray-600'}`}>
      {labels[source] ?? source}
    </span>
  )
}

// ── Severity Badge ─────────────────────────────────────────────────────────────
export const SeverityBadge = ({ severity }: { severity: string }) => {
  const styles: Record<string, string> = {
    critical: 'bg-red-100 text-red-800 border border-red-300',
    warning:  'bg-yellow-100 text-yellow-800 border border-yellow-300',
    info:     'bg-blue-100 text-blue-800 border border-blue-300',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold uppercase ${styles[severity] ?? ''}`}>
      {severity}
    </span>
  )
}

// ── Pipeline Step Bar ──────────────────────────────────────────────────────────
const STEPS = [
  { key: 'upload',    label: '📥 Upload' },
  { key: 'anomaly',   label: '🔍 Anomaly' },
  { key: 'verify',    label: '✏️ Verify' },
  { key: 'report',    label: '📄 Report' },
  { key: 'rulebook',  label: '📚 Rulebook' },
]

export const PipelineStatus = ({ currentStep }: { currentStep: string }) => {
  const stepMap: Record<string, number> = {
    start: 0, compliance_checked: 1, flags_reviewed: 2,
    rag_complete: 2, report_drafted: 3, report_finalised: 4,
  }
  const active = stepMap[currentStep] ?? 0
  return (
    <div className="flex items-center gap-1 text-sm">
      {STEPS.map((s, i) => (
        <React.Fragment key={s.key}>
          <span className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap
            ${i <= active ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-500'}`}>
            {s.label}
          </span>
          {i < STEPS.length - 1 && (
            <span className={`text-xs ${i < active ? 'text-indigo-400' : 'text-gray-300'}`}>→</span>
          )}
        </React.Fragment>
      ))}
    </div>
  )
}

// ── Card ───────────────────────────────────────────────────────────────────────
export const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-white border border-gray-200 rounded-xl shadow-sm p-6 ${className}`}>
    {children}
  </div>
)

// ── Section Heading ────────────────────────────────────────────────────────────
export const SectionHeading = ({ children }: { children: React.ReactNode }) => (
  <h2 className="text-lg font-semibold text-gray-900 mb-4">{children}</h2>
)

// ── Spinner ────────────────────────────────────────────────────────────────────
export const Spinner = ({ text = 'Loading...' }: { text?: string }) => (
  <div className="flex items-center gap-3 text-gray-500 py-8 justify-center">
    <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    <span>{text}</span>
  </div>
)

// ── Alert ──────────────────────────────────────────────────────────────────────
type AlertType = 'info' | 'success' | 'warning' | 'error'
export const Alert = ({ type, children }: { type: AlertType; children: React.ReactNode }) => {
  const styles: Record<AlertType, string> = {
    info:    'bg-blue-50  border-blue-300  text-blue-800',
    success: 'bg-green-50 border-green-300 text-green-800',
    warning: 'bg-yellow-50 border-yellow-300 text-yellow-800',
    error:   'bg-red-50   border-red-300   text-red-800',
  }
  return (
    <div className={`border rounded-lg p-4 text-sm ${styles[type]}`}>{children}</div>
  )
}

// ── RAG Chat Panel ─────────────────────────────────────────────────────────────
interface ChatTurn { question: string; answer: string; sources?: { source: string; page: number; relevance_score: number }[] }

export const RagChat = () => {
  const [history, setHistory] = React.useState<ChatTurn[]>([])
  const [input, setInput]     = React.useState('')
  const [loading, setLoading] = React.useState(false)

  const ask = async () => {
    if (!input.trim()) return
    const q = input.trim()
    setInput('')
    setLoading(true)
    try {
      const { chatQuery } = await import('../api/client')
      const res = await chatQuery(q)
      setHistory(h => [...h, { question: q, answer: res.answer, sources: res.sources }])
    } catch {
      setHistory(h => [...h, { question: q, answer: 'Error reaching the API.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="text-sm font-semibold text-gray-700 mb-2">💬 Ask the Rulebook</div>
      <div className="flex-1 overflow-y-auto space-y-3 mb-3 max-h-96">
        {history.map((t, i) => (
          <div key={i}>
            <div className="bg-indigo-50 rounded-lg p-2 text-xs text-indigo-800 mb-1">
              <span className="font-medium">You:</span> {t.question}
            </div>
            <div className="bg-gray-50 rounded-lg p-2 text-xs text-gray-700">
              <span className="font-medium">AI:</span> {t.answer}
              {t.sources && t.sources.length > 0 && (
                <div className="mt-1 text-gray-400">
                  {t.sources.slice(0, 2).map((s, j) => (
                    <div key={j}>📄 {s.source} p.{s.page} ({s.relevance_score.toFixed(2)})</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && <Spinner text="Searching rulebook..." />}
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && ask()}
          placeholder="e.g. What is CARO clause 3(ix)?"
          className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300"
        />
        <button onClick={ask} disabled={loading || !input.trim()}
          className="text-xs bg-indigo-600 text-white px-3 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-40">
          Ask
        </button>
      </div>
    </div>
  )
}
