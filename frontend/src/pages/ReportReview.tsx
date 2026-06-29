import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { downloadReport, finaliseReport, getReport, getSession, reviewFlags } from '../api/client'
import { Alert, Card, SectionHeading, Spinner } from '../components'

const SESSION_ID_KEY = 'arthAI_sessionId'

const STEP_ORDER = ['start', 'compliance_checked', 'flags_reviewed', 'rag_complete', 'report_drafted', 'report_finalised']
const isAtOrPast = (current: string, target: string) =>
  STEP_ORDER.indexOf(current) >= STEP_ORDER.indexOf(target)

const opinionStyles: Record<string, string> = {
  unmodified:           'bg-green-100 text-green-800 border border-green-200',
  qualified:            'bg-amber-100 text-amber-800 border border-amber-200',
  adverse:              'bg-red-100 text-red-800 border border-red-200',
  disclaimer_of_opinion:'bg-slate-200 text-slate-800 border border-slate-300',
}

type SignoffState = {
  firm_name: string; firm_reg: string; auditor_name: string
  membership_no: string; place: string; sign_date: string
}

const today = () => new Date().toISOString().slice(0, 10)

const ReportReview = () => {
  const navigate   = useNavigate()
  const sessionId  = localStorage.getItem(SESSION_ID_KEY)

  const [currentStep,    setCurrentStep]    = useState<string>('')
  const [anomalyFlags,   setAnomalyFlags]   = useState<{ rule_id: string }[]>([])
  const [report,         setReport]         = useState<Record<string, unknown> | null>(null)
  const [sectionValues,  setSectionValues]  = useState<Record<string, string>>({})
  const [signoff,        setSignoff]        = useState<SignoffState>({
    firm_name: '', firm_reg: '', auditor_name: '',
    membership_no: '', place: '', sign_date: today(),
  })
  const [loading,    setLoading]    = useState(true)
  const [generating, setGenerating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error,      setError]      = useState<string | null>(null)
  const [success,    setSuccess]    = useState<string | null>(null)

  // ── Load session state on mount ────────────────────────────────────────────
  useEffect(() => {
    if (!sessionId) { setLoading(false); return }
    let active = true

    const load = async () => {
      try {
        const state = await getSession(sessionId)
        if (!active) return
        setCurrentStep(state.current_step ?? '')
        setAnomalyFlags((state.anomaly_flags ?? []) as { rule_id: string }[])

        // If report already drafted, load it
        if (isAtOrPast(state.current_step ?? '', 'report_drafted')) {
          const r = await getReport(sessionId)
          if (!active) return
          setReport(r.report_sections)
          populateSections(r.report_sections)
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : 'Failed to load session.')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => { active = false }
  }, [sessionId])

  const populateSections = (reportSections: Record<string, unknown>) => {
    const s = (reportSections?.report_sections ?? {}) as Record<string, unknown>
    const olr = s.report_on_other_legal_requirements as { caro_observations?: string[] } | undefined
    const kam = s.key_audit_matters as { items?: string[] } | undefined

    const vals: Record<string, string> = {
      opinion:    String((s.opinion_section    as { body?: string })?.body ?? ''),
      basis:      String((s.basis_of_opinion   as { body?: string })?.body ?? ''),
      highlights: String((s.financial_highlights as { body?: string })?.body ?? ''),
      mgmt:       String((s.management_responsibility as { body?: string })?.body ?? ''),
      auditor:    String((s.auditor_responsibility    as { body?: string })?.body ?? ''),
      caro:       (olr?.caro_observations ?? []).join('\n'),
    }
    ;(kam?.items ?? []).forEach((item, i) => { vals[`kam_${i + 1}`] = item })
    setSectionValues(vals)
  }

  // ── Generate report (confirm all flags → RAG → Agent 4) ───────────────────
  const generateReport = async () => {
    if (!sessionId) return
    try {
      setGenerating(true); setError(null)

      // Confirm all anomaly flags (or use existing decisions from anomaly page)
      const decisions = anomalyFlags.map(f => ({ rule_id: f.rule_id, decision: 'confirm' as const }))
      await reviewFlags(sessionId, decisions)

      const r = await getReport(sessionId)
      setReport(r.report_sections)
      populateSections(r.report_sections)
      setCurrentStep('report_drafted')
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate report.')
    } finally {
      setGenerating(false)
    }
  }

  // ── Finalise ───────────────────────────────────────────────────────────────
  const finalise = async () => {
    if (!sessionId) return
    try {
      setSubmitting(true); setError(null)
      const resp = await finaliseReport(sessionId, { edits: sectionValues, ...signoff })
      setSuccess(`🎉 Report finalised. Saved to: ${resp.saved_to}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Finalisation failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const updateSection = (key: string, val: string) => {
    setSectionValues(c => ({ ...c, [key]: val }))
    setSuccess(null)
  }

  const sections     = (report?.report_sections ?? {}) as Record<string, unknown>
  const opinionType  = String(sections.overall_opinion_type ?? 'unmodified').toLowerCase()
  const companyName  = String(report?.company_name ?? '—')
  const financialYear= String(report?.financial_year ?? '—')
  const kamKeys = useMemo(
    () => Object.keys(sectionValues).filter(k => k.startsWith('kam_')).sort(),
    [sectionValues]
  )

  if (!sessionId) return (
    <Alert type="warning">No active session. Upload documents and complete the pipeline first.</Alert>
  )

  return (
    <div className="space-y-8">
      {loading && <Spinner text="Loading report state…" />}
      {error   && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      {/* ── Not yet at report stage ─────────────────────────────────────── */}
      {!loading && !isAtOrPast(currentStep, 'report_drafted') && !generating && (
        <Card>
          <SectionHeading>📄 Report Generation</SectionHeading>
          <div className="space-y-4 text-sm text-slate-600">
            <p>
              The report hasn't been generated yet for this session.
              Current pipeline step: <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{currentStep || 'start'}</code>
            </p>
            {!isAtOrPast(currentStep, 'compliance_checked') ? (
              <>
                <Alert type="warning">
                  Complete <strong>Anomaly Detection</strong> first — Agent 1 and Agent 2 need to run before the report can be drafted.
                </Alert>
                <button onClick={() => navigate('/anomaly')}
                  className="rounded-full bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">
                  Go to Anomaly Detection →
                </button>
              </>
            ) : (
              <>
                <Alert type="info">
                  {anomalyFlags.length > 0
                    ? `${anomalyFlags.length} anomaly flag(s) detected. You can review them on the Anomaly page, or generate the report now confirming all flags.`
                    : 'No anomaly flags detected. Ready to generate the report.'}
                </Alert>
                <div className="flex gap-3">
                  <button onClick={() => navigate('/anomaly')}
                    className="rounded-full border border-indigo-300 px-5 py-2.5 text-sm font-semibold text-indigo-700 hover:bg-indigo-50">
                    Review Flags First
                  </button>
                  <button onClick={() => void generateReport()}
                    className="rounded-full bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">
                    Generate Report Now
                  </button>
                </div>
              </>
            )}
          </div>
        </Card>
      )}

      {/* ── Generating spinner ──────────────────────────────────────────── */}
      {generating && (
        <Card>
          <Spinner text="Agent 3 fetching regulatory citations… Agent 4 drafting report…" />
          <p className="mt-2 text-center text-xs text-slate-400">This may take 20–40 seconds.</p>
        </Card>
      )}

      {/* ── Report editing UI ───────────────────────────────────────────── */}
      {!loading && !generating && report && (
        <>
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-widest text-slate-400">Audit draft</div>
                <h2 className="mt-1 text-2xl font-semibold text-slate-900">{companyName}</h2>
                <p className="text-sm text-slate-500">FY ending {financialYear}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`rounded-full px-4 py-2 text-sm font-semibold capitalize ${opinionStyles[opinionType] ?? opinionStyles.unmodified}`}>
                  {opinionType.replaceAll('_', ' ')}
                </span>
                <button onClick={() => downloadReport(sessionId!)}
                  className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                  ⬇️ Download draft
                </button>
              </div>
            </div>
          </Card>

          <Card>
            <SectionHeading>Edit report sections</SectionHeading>
            <p className="mb-6 text-xs text-slate-400 uppercase tracking-wide">Every section below requires auditor review before finalising</p>
            <div className="space-y-6">
              {([
                ['Opinion',                 'opinion',    8],
                ['Basis for Opinion',       'basis',      6],
                ['Financial Highlights',    'highlights', 5],
                ['Management Responsibility','mgmt',      6],
                ['Auditor Responsibility',  'auditor',    6],
                ['CARO Observations',       'caro',       5],
              ] as Array<[string, string, number]>).map(([label, key, rows]) => (
                <div key={key}>
                  <label className="block text-sm font-semibold text-slate-900">{label}</label>
                  <p className="mt-0.5 text-xs text-amber-600 uppercase tracking-wide">⚠️ Auditor review required</p>
                  <textarea
                    value={sectionValues[key] ?? ''}
                    onChange={e => updateSection(key, e.target.value)}
                    rows={rows}
                    className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
                  />
                </div>
              ))}

              {kamKeys.length > 0 && (
                <div>
                  <label className="block text-sm font-semibold text-slate-900">Key Audit Matters</label>
                  <p className="mt-0.5 text-xs text-amber-600 uppercase tracking-wide">⚠️ Auditor review required</p>
                  {kamKeys.map(key => (
                    <div key={key} className="mt-3">
                      <p className="text-xs text-slate-500 mb-1">{key.replace('_', ' ').toUpperCase()}</p>
                      <textarea
                        value={sectionValues[key] ?? ''}
                        onChange={e => updateSection(key, e.target.value)}
                        rows={5}
                        className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          {/* Sign-off */}
          <Card>
            <SectionHeading>Auditor Sign-off</SectionHeading>
            <p className="mb-4 text-xs text-red-600 uppercase tracking-wide">🔴 Complete before finalising</p>
            <div className="grid gap-4 sm:grid-cols-2">
              {([
                ['Firm Name',        'firm_name'],
                ['Firm Reg. No.',    'firm_reg'],
                ['Auditor Name',     'auditor_name'],
                ['Membership No.',   'membership_no'],
                ['Place',            'place'],
                ['Date',             'sign_date'],
              ] as Array<[string, keyof SignoffState]>).map(([label, key]) => (
                <div key={key}>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">{label}</label>
                  <input
                    type={key === 'sign_date' ? 'date' : 'text'}
                    value={signoff[key]}
                    onChange={e => setSignoff(s => ({ ...s, [key]: e.target.value }))}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
                  />
                </div>
              ))}
            </div>
          </Card>

          <div className="flex justify-end gap-3">
            <button onClick={() => downloadReport(sessionId!)}
              className="rounded-full border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              ⬇️ Download Draft
            </button>
            <button onClick={() => void finalise()} disabled={submitting}
              className="rounded-full bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
              {submitting ? 'Finalising…' : '✅ Finalise & Sign Report'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default ReportReview
