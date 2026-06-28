import { useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { getSession } from './api/client'
import { Alert, PipelineStatus, RagChat } from './components'
import AnomalyReview from './pages/AnomalyReview'
import Home from './pages/Home'
import Ingest from './pages/Ingest'
import ReportReview from './pages/ReportReview'
import Rulebook from './pages/Rulebook'
import VerifyFinancials from './pages/VerifyFinancials'

const SESSION_ID_KEY = 'arthAI_sessionId'
const SESSION_COMPANY_KEY = 'arthAI_sessionCompany'

const NAV_LINKS = [
  { to: '/', label: 'Dashboard' },
  { to: '/ingest', label: 'Ingest' },
  { to: '/anomaly', label: 'Anomaly Review' },
  { to: '/verify', label: 'Verify Financials' },
  { to: '/report', label: 'Report Review' },
  { to: '/rulebook', label: 'Rulebook' },
]

const routeStep = (pathname: string) => {
  if (pathname.startsWith('/report')) return 'report_drafted'
  if (pathname.startsWith('/verify')) return 'rag_complete'
  if (pathname.startsWith('/anomaly')) return 'compliance_checked'
  if (pathname.startsWith('/rulebook')) return 'report_finalised'
  return 'start'
}

const pageTitle = (pathname: string) => {
  if (pathname.startsWith('/ingest')) return 'Upload & Ingest'
  if (pathname.startsWith('/anomaly')) return 'Anomaly Detection'
  if (pathname.startsWith('/verify')) return 'Manual Financial Verification'
  if (pathname.startsWith('/report')) return 'Report Generation & Review'
  if (pathname.startsWith('/rulebook')) return 'Rulebook & Regulatory Search'
  return 'Financial Audit Dashboard'
}

const AuditLayout = () => {
  const location = useLocation()
  const [sessionId, setSessionId] = useState<string | null>(localStorage.getItem(SESSION_ID_KEY))
  const [sessionCompany, setSessionCompany] = useState<string | null>(localStorage.getItem(SESSION_COMPANY_KEY))
  const [sessionStep, setSessionStep] = useState<string | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)

  useEffect(() => {
    const syncSession = () => {
      setSessionId(localStorage.getItem(SESSION_ID_KEY))
      setSessionCompany(localStorage.getItem(SESSION_COMPANY_KEY))
    }

    syncSession()
    window.addEventListener('storage', syncSession)
    window.addEventListener('arthai-session-change', syncSession)
    return () => {
      window.removeEventListener('storage', syncSession)
      window.removeEventListener('arthai-session-change', syncSession)
    }
  }, [])

  useEffect(() => {
    let active = true

    const loadStep = async () => {
      if (!sessionId) {
        setSessionStep(null)
        setSessionError(null)
        return
      }

      try {
        const state = await getSession(sessionId)
        if (!active) return
        setSessionStep(state.current_step)
        setSessionError(null)
        const nextCompany = typeof state.financial_json?.company_name === 'string'
          ? state.financial_json.company_name
          : sessionCompany
        if (nextCompany) {
          localStorage.setItem(SESSION_COMPANY_KEY, nextCompany)
          setSessionCompany(nextCompany)
        }
      } catch (error) {
        if (!active) return
        setSessionError(error instanceof Error ? error.message : 'Unable to load active session.')
      }
    }

    void loadStep()
    return () => {
      active = false
    }
  }, [location.pathname, sessionCompany, sessionId])

  const pipelineStep = useMemo(() => sessionStep ?? routeStep(location.pathname), [location.pathname, sessionStep])

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-4">
          <div className="flex items-center gap-4">
            <Link to="/" className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-600 text-xl text-white shadow-sm">अ</div>
              <div>
                <div className="text-lg font-semibold tracking-tight text-slate-900">अर्थAI</div>
                <div className="text-xs text-slate-500">Financial Audit Platform</div>
              </div>
            </Link>
            <nav className="hidden items-center gap-2 lg:flex">
              {NAV_LINKS.map(link => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.to === '/'}
                  className={({ isActive }) => [
                    'rounded-full px-4 py-2 text-sm font-medium transition-colors',
                    isActive ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-indigo-50 hover:text-indigo-700',
                  ].join(' ')}
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3 rounded-full border border-indigo-100 bg-indigo-50 px-4 py-2 text-sm text-indigo-900">
            <span className="h-2.5 w-2.5 rounded-full bg-indigo-600" />
            <span className="font-medium">Active session:</span>
            <span>{sessionCompany || sessionId || 'None selected'}</span>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-8 px-6 py-8 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <main className="min-w-0 space-y-6">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">Audit workspace</p>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{pageTitle(location.pathname)}</h1>
              </div>
              <PipelineStatus currentStep={pipelineStep} />
            </div>
          </div>

          {sessionError && (
            <Alert type="warning">
              Active session sync failed: {sessionError}
            </Alert>
          )}

          <Outlet />
        </main>

        <aside className="xl:sticky xl:top-28 xl:h-[calc(100vh-8rem)]">
          <div className="flex h-full flex-col gap-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div>
              <p className="text-sm font-semibold text-slate-900">Pipeline assistant</p>
              <p className="mt-1 text-sm text-slate-500">Use the regulatory chat at any stage to validate audit decisions and rulebook references.</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              <div className="font-medium text-slate-900">Current session</div>
              <div className="mt-2 break-all">{sessionId || 'No session selected'}</div>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              <RagChat />
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AuditLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/ingest" element={<Ingest />} />
          <Route path="/anomaly" element={<AnomalyReview />} />
          <Route path="/verify" element={<VerifyFinancials />} />
          <Route path="/report" element={<ReportReview />} />
          <Route path="/rulebook" element={<Rulebook />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
