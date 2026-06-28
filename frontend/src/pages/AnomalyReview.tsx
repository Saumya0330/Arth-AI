import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getSession, reviewFlags, type AnomalyFlag, type PipelineState } from '../api/client'
import { Alert, Card, SectionHeading, SeverityBadge, Spinner } from '../components'

const SESSION_ID_KEY = 'arthAI_sessionId'
const SESSION_COMPANY_KEY = 'arthAI_sessionCompany'

type DecisionState = Record<string, { decision: 'confirm' | 'dismiss' | 'escalate'; note: string }>

type CitationFlag = AnomalyFlag & {
  regulatory_passages?: { source: string; page: number; relevance_score: number; content: string }[]
  regulatory_response?: string
}

const loadSessionId = () => localStorage.getItem(SESSION_ID_KEY)

const AnomalyReview = () => {
  const [sessionId] = useState<string | null>(loadSessionId())
  const [state, setState] = useState<PipelineState | null>(null)
  const [decisions, setDecisions] = useState<DecisionState>({})
  const [citations, setCitations] = useState<CitationFlag[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    const load = async () => {
      if (!sessionId) {
        setLoading(false)
        return
      }

      try {
        const session = await getSession(sessionId)
        if (!active) return
        setState(session)
        setCitations((session.flags_with_citations as CitationFlag[] | undefined) ?? [])
        const companyName = typeof session.financial_json?.company_name === 'string' ? session.financial_json.company_name : null
        if (companyName) {
          localStorage.setItem(SESSION_COMPANY_KEY, companyName)
          window.dispatchEvent(new Event('arthai-session-change'))
        }
        const nextDecisions = (session.anomaly_flags ?? []).reduce<DecisionState>((accumulator, flag) => {
          accumulator[flag.rule_id] = { decision: 'confirm', note: '' }
          return accumulator
        }, {})
        setDecisions(nextDecisions)
        setError(null)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Unable to load anomaly review data.')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [sessionId])

  const flags = state?.anomaly_flags ?? []
  const summary = useMemo(() => {
    const sessionFlags = state?.anomaly_flags ?? []
    return {
      critical: sessionFlags.filter(flag => flag.severity === 'critical').length,
      warning: sessionFlags.filter(flag => flag.severity === 'warning').length,
      total: sessionFlags.length,
    }
  }, [state])

  const updateDecision = (ruleId: string, updates: Partial<DecisionState[string]>) => {
    setDecisions(current => ({
      ...current,
      [ruleId]: {
        decision: current[ruleId]?.decision ?? 'confirm',
        note: current[ruleId]?.note ?? '',
        ...updates,
      },
    }))
  }

  const submitReview = async () => {
    if (!sessionId) return

    try {
      setSubmitting(true)
      setError(null)
      const payload = flags.map(flag => ({
        rule_id: flag.rule_id,
        decision: decisions[flag.rule_id]?.decision ?? 'confirm',
        note: decisions[flag.rule_id]?.note.trim() || undefined,
      }))
      const response = await reviewFlags(sessionId, payload)
      setCitations((response.flags_with_citations as CitationFlag[] | undefined) ?? [])
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to submit flag decisions.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!sessionId) {
    return (
      <Alert type="warning">
        No active session found. <Link to="/ingest" className="font-semibold text-indigo-700">Upload a PDF to begin.</Link>
      </Alert>
    )
  }

  return (
    <div className="space-y-8">
      {loading && <Spinner text="Loading anomaly flags..." />}
      {error && <Alert type="error">{error}</Alert>}

      {!loading && state && (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="bg-slate-50">
              <div className="text-xs uppercase tracking-wide text-slate-500">Critical</div>
              <div className="mt-2 text-3xl font-semibold text-red-600">{summary.critical}</div>
            </Card>
            <Card className="bg-slate-50">
              <div className="text-xs uppercase tracking-wide text-slate-500">Warnings</div>
              <div className="mt-2 text-3xl font-semibold text-amber-600">{summary.warning}</div>
            </Card>
            <Card className="bg-slate-50">
              <div className="text-xs uppercase tracking-wide text-slate-500">Total flags</div>
              <div className="mt-2 text-3xl font-semibold text-slate-900">{summary.total}</div>
            </Card>
          </div>

          {flags.length === 0 ? (
            <Alert type="success">No anomaly flags were returned for this session. You can proceed directly to manual verification.</Alert>
          ) : (
            <div className="space-y-5">
              {flags.map(flag => {
                const current = decisions[flag.rule_id] ?? { decision: 'confirm' as const, note: '' }
                return (
                  <Card key={flag.rule_id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-3">
                          <code className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{flag.rule_id}</code>
                          <SeverityBadge severity={flag.severity} />
                        </div>
                        <h3 className="mt-4 text-lg font-semibold text-slate-900">{flag.description}</h3>
                      </div>
                    </div>

                    <div className="mt-5 grid gap-4 lg:grid-cols-3">
                      <div className="rounded-2xl bg-slate-50 p-4">
                        <div className="text-xs uppercase tracking-wide text-slate-500">Field</div>
                        <div className="mt-2 text-sm font-medium text-slate-900">{flag.field || '—'}</div>
                      </div>
                      <div className="rounded-2xl bg-slate-50 p-4">
                        <div className="text-xs uppercase tracking-wide text-slate-500">Expected</div>
                        <div className="mt-2 text-sm font-medium text-slate-900">{flag.expected || '—'}</div>
                      </div>
                      <div className="rounded-2xl bg-slate-50 p-4">
                        <div className="text-xs uppercase tracking-wide text-slate-500">Actual</div>
                        <div className="mt-2 text-sm font-medium text-slate-900">{flag.actual || '—'}</div>
                      </div>
                    </div>

                    <div className="mt-6 rounded-2xl border border-slate-200 p-5">
                      <div className="text-sm font-semibold text-slate-900">Auditor decision</div>
                      <div className="mt-4 flex flex-wrap gap-3">
                        {[
                          { value: 'confirm', label: '✅ Confirm' },
                          { value: 'dismiss', label: '❌ Dismiss' },
                          { value: 'escalate', label: '⚡ Escalate' },
                        ].map(option => (
                          <label
                            key={option.value}
                            className={[
                              'inline-flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition',
                              current.decision === option.value
                                ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                                : 'border-slate-200 text-slate-600 hover:border-indigo-200 hover:bg-slate-50',
                            ].join(' ')}
                          >
                            <input
                              type="radio"
                              className="sr-only"
                              checked={current.decision === option.value}
                              onChange={() => updateDecision(flag.rule_id, { decision: option.value as DecisionState[string]['decision'] })}
                            />
                            {option.label}
                          </label>
                        ))}
                      </div>

                      <label className="mt-4 block text-sm font-medium text-slate-700">
                        Note (optional)
                        <input
                          type="text"
                          value={current.note}
                          onChange={event => updateDecision(flag.rule_id, { note: event.target.value })}
                          className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                          placeholder="Record materiality, rationale, or next action"
                        />
                      </label>
                    </div>
                  </Card>
                )
              })}

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => void submitReview()}
                  disabled={submitting}
                  className="rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Submit decisions
                </button>
              </div>
            </div>
          )}

          {submitting && (
            <Card>
              <Spinner text="Running Agent 3 (RAG) for regulatory citations..." />
            </Card>
          )}

          {citations.length > 0 && (
            <Card>
              <SectionHeading>Regulatory citations for confirmed flags</SectionHeading>
              <div className="space-y-5">
                {citations.map(flag => (
                  <div key={flag.rule_id} className="rounded-3xl border border-slate-200 p-5">
                    <div className="flex items-center gap-3">
                      <code className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{flag.rule_id}</code>
                      <SeverityBadge severity={flag.severity} />
                    </div>
                    <p className="mt-4 text-sm font-medium text-slate-900">{flag.description}</p>

                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                      {(flag.regulatory_passages ?? []).map(passage => (
                        <div key={`${flag.rule_id}-${passage.source}-${passage.page}`} className="rounded-2xl bg-slate-50 p-4 text-sm">
                          <div className="font-semibold text-slate-900">{passage.source}</div>
                          <div className="mt-1 text-slate-500">Page {passage.page} · Relevance {passage.relevance_score.toFixed(2)}</div>
                          <p className="mt-3 text-slate-700">{passage.content}</p>
                        </div>
                      ))}
                    </div>

                    {flag.regulatory_response && (
                      <div className="mt-4 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
                        <div className="font-semibold">AI response</div>
                        <p className="mt-2 whitespace-pre-wrap">{flag.regulatory_response}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          <div className="flex justify-end">
            <Link to="/verify" className="rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700">
              Proceed to Verify Financials →
            </Link>
          </div>
        </>
      )}
    </div>
  )
}

export default AnomalyReview
