import { useEffect, useMemo, useState } from 'react'
import { downloadReport, finaliseReport, getReport } from '../api/client'
import { Alert, Card, SectionHeading, Spinner } from '../components'

const SESSION_ID_KEY = 'arthAI_sessionId'

const opinionStyles: Record<string, string> = {
  unmodified: 'bg-green-100 text-green-800 border border-green-200',
  qualified: 'bg-amber-100 text-amber-800 border border-amber-200',
  adverse: 'bg-red-100 text-red-800 border border-red-200',
  disclaimer_of_opinion: 'bg-slate-200 text-slate-800 border border-slate-300',
}

type ReportResponse = Awaited<ReturnType<typeof getReport>>

type SignoffState = {
  firm_name: string
  firm_reg: string
  auditor_name: string
  membership_no: string
  place: string
  sign_date: string
}

const today = () => new Date().toISOString().slice(0, 10)

const ReportReview = () => {
  const sessionId = localStorage.getItem(SESSION_ID_KEY)
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [sectionValues, setSectionValues] = useState<Record<string, string>>({})
  const [signoff, setSignoff] = useState<SignoffState>({
    firm_name: '',
    firm_reg: '',
    auditor_name: '',
    membership_no: '',
    place: '',
    sign_date: today(),
  })
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    const load = async () => {
      if (!sessionId) {
        setLoading(false)
        return
      }

      try {
        const response = await getReport(sessionId)
        if (!active) return
        setReport(response)
        const sections = response.report_sections?.report_sections as Record<string, unknown> | undefined
        const legalRequirements = sections?.report_on_other_legal_requirements as { caro_observations?: string[] } | undefined
        const keyAuditMatters = sections?.key_audit_matters as { items?: string[] } | undefined
        const nextValues: Record<string, string> = {
          opinion: typeof sections?.opinion_section === 'object' && sections?.opinion_section && 'body' in sections.opinion_section
            ? String((sections.opinion_section as { body?: string }).body ?? '')
            : '',
          basis: typeof sections?.basis_of_opinion === 'object' && sections?.basis_of_opinion && 'body' in sections.basis_of_opinion
            ? String((sections.basis_of_opinion as { body?: string }).body ?? '')
            : '',
          highlights: typeof sections?.financial_highlights === 'object' && sections?.financial_highlights && 'body' in sections.financial_highlights
            ? String((sections.financial_highlights as { body?: string }).body ?? '')
            : '',
          mgmt: typeof sections?.management_responsibility === 'object' && sections?.management_responsibility && 'body' in sections.management_responsibility
            ? String((sections.management_responsibility as { body?: string }).body ?? '')
            : '',
          auditor: typeof sections?.auditor_responsibility === 'object' && sections?.auditor_responsibility && 'body' in sections.auditor_responsibility
            ? String((sections.auditor_responsibility as { body?: string }).body ?? '')
            : '',
          caro: Array.isArray(legalRequirements?.caro_observations)
            ? (legalRequirements.caro_observations ?? []).join('\n')
            : '',
        }
        const kamItems = Array.isArray(keyAuditMatters?.items) ? (keyAuditMatters.items ?? []) : []
        kamItems.forEach((item, index) => {
          nextValues[`kam_${index + 1}`] = item
        })
        setSectionValues(nextValues)
        setError(null)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Unable to load the report draft.')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [sessionId])

  const sections = report?.report_sections?.report_sections as Record<string, unknown> | undefined
  const opinionType = String(sections?.overall_opinion_type ?? 'unmodified').toLowerCase()
  const companyName = String(report?.report_sections?.company_name ?? '—')
  const financialYear = String(report?.report_sections?.financial_year ?? '—')
  const kamKeys = useMemo(() => Object.keys(sectionValues).filter(key => key.startsWith('kam_')).sort(), [sectionValues])

  const updateSection = (key: string, value: string) => {
    setSectionValues(current => ({ ...current, [key]: value }))
    setSuccess(null)
  }

  const finalise = async () => {
    if (!sessionId) return

    try {
      setSubmitting(true)
      const response = await finaliseReport(sessionId, {
        edits: sectionValues,
        ...signoff,
      })
      setSuccess(`🎉 Report finalised successfully. Saved to ${response.saved_to}.`)
      setError(null)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to finalise the report.')
      setSuccess(null)
    } finally {
      setSubmitting(false)
    }
  }

  if (!sessionId) {
    return <Alert type="warning">No active session found. Upload a PDF and complete the audit workflow first.</Alert>
  }

  return (
    <div className="space-y-8">
      {loading && <Spinner text="Loading audit report draft..." />}
      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      {!loading && report && (
        <>
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-sm uppercase tracking-[0.2em] text-slate-500">Audit draft</div>
                <h2 className="mt-2 text-2xl font-semibold text-slate-900">{companyName}</h2>
                <p className="mt-1 text-sm text-slate-500">Financial year ending {financialYear}</p>
              </div>
              <span className={['rounded-full px-4 py-2 text-sm font-semibold capitalize', opinionStyles[opinionType] ?? opinionStyles.unmodified].join(' ')}>
                {opinionType.replaceAll('_', ' ')}
              </span>
            </div>
          </Card>

          <Card>
            <SectionHeading>Report sections</SectionHeading>
            <div className="space-y-6">
              {([
                ['Opinion', 'opinion', 180],
                ['Basis for Opinion', 'basis', 180],
                ['Financial Highlights', 'highlights', 180],
                ['Management Responsibility', 'mgmt', 160],
                ['Auditor Responsibility', 'auditor', 180],
                ['CARO Observations', 'caro', 180],
              ] as Array<[string, string, number]>).map(([label, key, height]) => (
                <div key={key}>
                  <label className="block text-sm font-semibold text-slate-900">{label}</label>
                  <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">AUDITOR: REVIEW REQUIRED</p>
                  <textarea
                    value={sectionValues[key] ?? ''}
                    onChange={event => updateSection(key, event.target.value)}
                    rows={Number(height) / 20}
                    className="mt-3 w-full rounded-3xl border border-slate-200 px-4 py-4 text-sm outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                  />
                </div>
              ))}

              <div>
                <label className="block text-sm font-semibold text-slate-900">Key Audit Matters</label>
                <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">AUDITOR: REVIEW REQUIRED</p>
                <div className="mt-3 space-y-4">
                  {kamKeys.map(key => (
                    <textarea
                      key={key}
                      value={sectionValues[key] ?? ''}
                      onChange={event => updateSection(key, event.target.value)}
                      rows={6}
                      className="w-full rounded-3xl border border-slate-200 px-4 py-4 text-sm outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                    />
                  ))}
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <SectionHeading>Auditor sign-off</SectionHeading>
            <div className="grid gap-4 lg:grid-cols-2">
              {[
                ['firm_name', 'Firm name'],
                ['firm_reg', 'Firm registration no.'],
                ['auditor_name', 'Auditor name'],
                ['membership_no', 'Membership no.'],
                ['place', 'Place'],
              ].map(([key, label]) => (
                <label key={key} className="block text-sm font-medium text-slate-700">
                  {label}
                  <input
                    type="text"
                    value={signoff[key as keyof SignoffState]}
                    onChange={event => setSignoff(current => ({ ...current, [key]: event.target.value }))}
                    className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                  />
                </label>
              ))}
              <label className="block text-sm font-medium text-slate-700">
                Date
                <input
                  type="date"
                  value={signoff.sign_date}
                  onChange={event => setSignoff(current => ({ ...current, sign_date: event.target.value }))}
                  className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                />
              </label>
            </div>
          </Card>

          <div className="flex flex-wrap justify-end gap-3">
            <button
              type="button"
              onClick={() => {
                if (sessionId) downloadReport(sessionId)
              }}
              className="rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Download Draft
            </button>
            <button
              type="button"
              onClick={() => void finalise()}
              disabled={submitting}
              className="rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Finalising...' : 'Finalise & Sign Report'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default ReportReview
