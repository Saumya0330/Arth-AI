import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listSessions, type Session } from '../api/client'
import { Alert, Card, Spinner } from '../components'

const SESSION_ID_KEY = 'arthAI_sessionId'
const SESSION_COMPANY_KEY = 'arthAI_sessionCompany'

const routeForPipelineStep = (step: string) => {
  if (step === 'report_generated') return '/report'
  if (step === 'rag_complete') return '/verify'
  return '/anomaly'
}

const formatConfidence = (value: number) => `${Math.round((value || 0) * 100)}%`

const pipelineLabel = (step: string) => {
  if (step === 'report_generated') return 'Report Draft Ready'
  if (step === 'rag_complete') return 'Regulatory Review Complete'
  return 'Extraction Complete'
}

const Home = () => {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(localStorage.getItem(SESSION_ID_KEY))

  useEffect(() => {
    const syncActive = () => setActiveSessionId(localStorage.getItem(SESSION_ID_KEY))
    window.addEventListener('storage', syncActive)
    window.addEventListener('arthai-session-change', syncActive)
    return () => {
      window.removeEventListener('storage', syncActive)
      window.removeEventListener('arthai-session-change', syncActive)
    }
  }, [])

  useEffect(() => {
    let active = true

    const loadSessions = async () => {
      try {
        setLoading(true)
        const data = await listSessions()
        if (!active) return
        setSessions(data)
        setError(null)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Unable to load audit sessions.')
      } finally {
        if (active) setLoading(false)
      }
    }

    void loadSessions()
    return () => {
      active = false
    }
  }, [])

  const activeSession = useMemo(
    () => sessions.find(session => session.session_id === activeSessionId),
    [activeSessionId, sessions],
  )

  const resumeSession = (session: Session) => {
    localStorage.setItem(SESSION_ID_KEY, session.session_id)
    localStorage.setItem(SESSION_COMPANY_KEY, session.company_name)
    window.dispatchEvent(new Event('arthai-session-change'))
    navigate(routeForPipelineStep(session.pipeline_step))
  }

  return (
    <div className="space-y-8">
      <Card className="border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-white">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">📊 अर्थAI — Financial Audit Platform</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">Audit sessions, extraction status, and report readiness in one workspace.</h2>
            <p className="mt-3 text-sm text-slate-600">Thapar Institute · CPG327</p>
          </div>
          <Link
            to="/ingest"
            className="inline-flex items-center rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700"
          >
            + New audit
          </Link>
        </div>
      </Card>

      {activeSession && (
        <Alert type="info">
          Active session: <strong>{activeSession.company_name}</strong> · {activeSession.financial_year} · {pipelineLabel(activeSession.pipeline_step)}
        </Alert>
      )}

      {loading && <Spinner text="Loading previous audit sessions..." />}

      {error && (
        <Alert type="error">
          {error}
        </Alert>
      )}

      {!loading && !error && sessions.length === 0 && (
        <Card>
          <p className="text-lg font-semibold text-slate-900">No audits yet</p>
          <p className="mt-2 text-sm text-slate-500">Upload your first financial statement PDF to create an audit session.</p>
        </Card>
      )}

      {!loading && !error && sessions.length > 0 && (
        <div className="grid gap-5 lg:grid-cols-2">
          {sessions.map(session => {
            const isActive = session.session_id === activeSessionId
            return (
              <Card
                key={session.session_id}
                className={[
                  'transition',
                  isActive ? 'border-indigo-400 ring-2 ring-indigo-100' : 'hover:border-indigo-200',
                ].join(' ')}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <h3 className="text-xl font-semibold text-slate-900">{session.company_name}</h3>
                      {isActive && (
                        <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-700">Active</span>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-slate-500">Session ID: {session.session_id}</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">{pipelineLabel(session.pipeline_step)}</span>
                </div>

                <div className="mt-6 grid gap-4 sm:grid-cols-3">
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Financial year</div>
                    <div className="mt-2 text-lg font-semibold text-slate-900">{session.financial_year || '—'}</div>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Confidence</div>
                    <div className="mt-2 text-lg font-semibold text-slate-900">{formatConfidence(session.extraction_confidence)}</div>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Pipeline</div>
                    <div className="mt-2 text-lg font-semibold text-slate-900">{session.pipeline_step}</div>
                  </div>
                </div>

                <div className="mt-6 flex items-center justify-between gap-4">
                  <p className="text-sm text-slate-500">Resume from the latest completed step for this audit trail.</p>
                  <button
                    type="button"
                    onClick={() => resumeSession(session)}
                    className="inline-flex items-center rounded-full border border-indigo-200 px-4 py-2 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-50"
                  >
                    Resume
                  </button>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default Home
