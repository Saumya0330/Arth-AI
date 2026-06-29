import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSession, uploadPDF, type MathCheck, type PipelineState } from '../api/client'
import { Alert, Card, SectionHeading, SourceBadge, Spinner } from '../components'

const SESSION_ID_KEY      = 'arthAI_sessionId'
const SESSION_COMPANY_KEY = 'arthAI_sessionCompany'
const STATUS_MESSAGES     = [
  'Saving files…',
  'Extracting text (OCR if scanned)…',
  'Running LLM to complete financial fields…',
  'Agent 1: validating arithmetic…',
  'Agent 2: checking compliance rules…',
  'Pipeline ready — loading results…',
]

const ALLOWED_TYPES = ['.pdf', '.csv', '.xlsx', '.xls']

const getByPath = (record: Record<string, unknown> | undefined, path: string): unknown => {
  return path.split('.').reduce<unknown>((acc, key) => {
    if (!acc || typeof acc !== 'object') return undefined
    return (acc as Record<string, unknown>)[key]
  }, record)
}

const formatValue = (val: unknown): string => {
  if (val === null || val === undefined || val === '') return '—'
  if (typeof val === 'number') return val.toLocaleString('en-IN')
  return String(val)
}

const Ingest = () => {
  const navigate  = useNavigate()
  const inputRef  = useRef<HTMLInputElement | null>(null)

  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [dragActive,    setDragActive]    = useState(false)
  const [uploading,     setUploading]     = useState(false)
  const [statusIndex,   setStatusIndex]   = useState(0)
  const [error,         setError]         = useState<string | null>(null)
  const [session,       setSession]       = useState<PipelineState | null>(null)
  const [uploadMeta,    setUploadMeta]    = useState<{ source_files?: string[] } | null>(null)

  // ── Load existing session on mount ─────────────────────────────────────────
  useEffect(() => {
    const id = localStorage.getItem(SESSION_ID_KEY)
    if (!id) return
    getSession(id)
      .then(s => { setSession(s); setUploadMeta(null) })
      .catch(() => {/* session not found — ignore */})
  }, [])

  // ── Status message cycling ─────────────────────────────────────────────────
  useEffect(() => {
    if (!uploading) return
    const t = window.setInterval(() =>
      setStatusIndex(i => (i + 1) % STATUS_MESSAGES.length), 2000)
    return () => window.clearInterval(t)
  }, [uploading])

  // ── Derived data ───────────────────────────────────────────────────────────
  const fieldGroups = useMemo(() => {
    const src = session?.field_sources ?? {}
    return {
      regex:    Object.entries(src).filter(([, v]) => v === 'regex'),
      llm:      Object.entries(src).filter(([, v]) => v === 'llm'),
      verified: Object.entries(src).filter(([, v]) => v === 'auditor_verified'),
    }
  }, [session])

  const auditObs = useMemo(() => {
    const o = session?.financial_json?.audit_observations
    return Array.isArray(o) ? o as string[] : []
  }, [session])

  const mathReport  = session?.math_report
  const companyInfo = session?.financial_json ?? {}
  const companyName = typeof companyInfo.company_name === 'string' ? companyInfo.company_name : '—'

  // ── File handling ──────────────────────────────────────────────────────────
  const validateFiles = useCallback((incoming: FileList | File[]): File[] => {
    const arr = Array.from(incoming)
    const bad = arr.filter(f => !ALLOWED_TYPES.some(ext => f.name.toLowerCase().endsWith(ext)))
    if (bad.length) {
      setError(`Unsupported file type(s): ${bad.map(f => f.name).join(', ')}. Allowed: PDF, CSV, XLSX`)
      return []
    }
    return arr
  }, [])

  const handleFiles = useCallback((incoming: FileList | File[]) => {
    const valid = validateFiles(incoming)
    if (!valid.length) return
    setSelectedFiles(valid)
    setError(null)
    setSession(null)
    setUploadMeta(null)
  }, [validateFiles])

  // ── Upload ─────────────────────────────────────────────────────────────────
  const startUpload = async () => {
    if (!selectedFiles.length) { setError('Select at least one file.'); return }
    try {
      setUploading(true); setStatusIndex(0); setError(null)
      const summary  = await uploadPDF(selectedFiles)
      const newState = await getSession(summary.session_id)
      localStorage.setItem(SESSION_ID_KEY, summary.session_id)
      if (summary.company_name) localStorage.setItem(SESSION_COMPANY_KEY, summary.company_name)
      window.dispatchEvent(new Event('arthai-session-change'))
      setSession(newState)
      setUploadMeta(summary)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  // ── Field table ────────────────────────────────────────────────────────────
  const FieldTable = ({ rows, source }: { rows: [string, string][]; source: string }) => (
    <div className="overflow-auto rounded-xl border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-slate-500 text-xs">
          <tr>
            <th className="px-4 py-2 font-medium">Field</th>
            <th className="px-4 py-2 font-medium">Value</th>
            <th className="px-4 py-2 font-medium">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map(([path]) => (
            <tr key={path} className="hover:bg-slate-50">
              <td className="px-4 py-2 font-mono text-xs text-slate-600">{path}</td>
              <td className="px-4 py-2 font-medium text-slate-900">
                {formatValue(getByPath(session?.financial_json, path))}
              </td>
              <td className="px-4 py-2"><SourceBadge source={source} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return (
    <div className="space-y-8">

      {/* ── Upload card ── */}
      <Card>
        <SectionHeading>Upload financial documents</SectionHeading>
        <p className="mb-5 text-sm text-slate-500">
          Upload one or more documents for this audit.
          Supported: <code className="rounded bg-slate-100 px-1">PDF</code>{' '}
          <code className="rounded bg-slate-100 px-1">CSV</code>{' '}
          <code className="rounded bg-slate-100 px-1">XLSX</code>.
          Multiple files are merged into one session.
        </p>

        <div
          onDragOver={e => { e.preventDefault(); setDragActive(true) }}
          onDragLeave={() => setDragActive(false)}
          onDrop={e => { e.preventDefault(); setDragActive(false); handleFiles(e.dataTransfer.files) }}
          onClick={() => inputRef.current?.click()}
          className={[
            'flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-8 py-12 text-center transition',
            dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 hover:border-indigo-300 hover:bg-slate-50',
          ].join(' ')}
        >
          <div className="text-4xl">📂</div>
          <h3 className="mt-3 text-lg font-semibold text-slate-900">
            Drag and drop files here
          </h3>
          <p className="mt-1 text-sm text-slate-500">PDF · CSV · XLSX — multiple files supported</p>
          <button type="button" className="mt-5 rounded-full bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">
            Browse files
          </button>
          <input
            ref={inputRef} type="file" multiple className="hidden"
            accept=".pdf,.csv,.xlsx,.xls"
            onChange={e => handleFiles(e.target.files ?? [])}
          />
        </div>

        {selectedFiles.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedFiles.map(f => (
              <span key={f.name} className="flex items-center gap-1 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-800">
                📄 {f.name}
                <button onClick={e => { e.stopPropagation(); setSelectedFiles(prev => prev.filter(x => x !== f)) }}
                  className="ml-1 text-indigo-400 hover:text-red-500">✕</button>
              </span>
            ))}
          </div>
        )}

        <div className="mt-5 flex justify-end">
          <button type="button" onClick={() => void startUpload()}
            disabled={uploading || !selectedFiles.length}
            className="rounded-full bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed">
            Start audit pipeline
          </button>
        </div>
      </Card>

      {error && <Alert type="error">{error}</Alert>}

      {uploading && (
        <Card>
          <Spinner text={STATUS_MESSAGES[statusIndex]} />
          <p className="mt-2 text-center text-xs text-slate-400">
            Large scanned PDFs may take 2–4 minutes. Please wait.
          </p>
        </Card>
      )}

      {/* ── Results (shown after upload OR on session resume) ── */}
      {session && !uploading && (
        <>
          {uploadMeta?.source_files && (
            <Alert type="success">
              Processed: {uploadMeta.source_files.join(' + ')}
            </Alert>
          )}

          {/* Company info */}
          <Card>
            <SectionHeading>Company & extraction summary</SectionHeading>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ['Company',       companyName],
                ['CIN',           formatValue(companyInfo.cin)],
                ['Financial Year',formatValue(companyInfo.financial_year_end)],
                ['Auditor',       formatValue(companyInfo.auditor_name)],
              ].map(([label, val]) => (
                <div key={label} className="rounded-xl bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
                  <div className="mt-1 text-sm font-semibold text-slate-900 break-words">{val}</div>
                </div>
              ))}
            </div>
            <div className="mt-5">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-600">Extraction confidence</span>
                <span className="font-semibold text-indigo-700">
                  {Math.round(((session.financial_json?.extraction_confidence as number) ?? 0) * 100)}%
                </span>
              </div>
              <div className="h-2.5 rounded-full bg-slate-100">
                <div className="h-2.5 rounded-full bg-indigo-600 transition-all"
                  style={{ width: `${Math.round(((session.financial_json?.extraction_confidence as number) ?? 0) * 100)}%` }} />
              </div>
            </div>
          </Card>

          {/* Math validation — Agent 1 */}
          <Card>
            <SectionHeading>🔢 Math Validation — Agent 1 (Pure Python, no LLM)</SectionHeading>
            {mathReport ? (
              <>
                <div className="mb-4 grid grid-cols-3 gap-3">
                  <div className="rounded-xl bg-slate-50 p-3 text-center">
                    <div className="text-2xl font-bold text-slate-900">{mathReport.total_checks}</div>
                    <div className="text-xs text-slate-500 mt-1">Total checks</div>
                  </div>
                  <div className="rounded-xl bg-green-50 p-3 text-center">
                    <div className="text-2xl font-bold text-green-700">{mathReport.passed}</div>
                    <div className="text-xs text-slate-500 mt-1">Passed</div>
                  </div>
                  <div className={`rounded-xl p-3 text-center ${mathReport.failed > 0 ? 'bg-red-50' : 'bg-slate-50'}`}>
                    <div className={`text-2xl font-bold ${mathReport.failed > 0 ? 'text-red-600' : 'text-slate-700'}`}>{mathReport.failed}</div>
                    <div className="text-xs text-slate-500 mt-1">Failed</div>
                  </div>
                </div>
                {mathReport.has_critical_errors && (
                  <Alert type="error">Critical arithmetic errors found — review in Anomaly Detection.</Alert>
                )}
                {(mathReport.checks as MathCheck[]).length > 0 && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm font-medium text-slate-700 hover:text-indigo-600">
                      View all {(mathReport.checks as MathCheck[]).length} check(s)
                    </summary>
                    <div className="mt-3 overflow-auto rounded-xl border border-slate-200">
                      <table className="min-w-full divide-y divide-slate-200 text-sm">
                        <thead className="bg-slate-50 text-xs text-slate-500">
                          <tr>
                            <th className="px-4 py-2 text-left font-medium">Check</th>
                            <th className="px-4 py-2 text-left font-medium">Result</th>
                            <th className="px-4 py-2 text-left font-medium">Expected</th>
                            <th className="px-4 py-2 text-left font-medium">Actual</th>
                            <th className="px-4 py-2 text-left font-medium">Diff</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 bg-white">
                          {(mathReport.checks as MathCheck[]).map(c => (
                            <tr key={c.check} className={c.critical && !c.passed ? 'bg-red-50' : ''}>
                              <td className="px-4 py-2 text-slate-800">{c.check}</td>
                              <td className="px-4 py-2">
                                <span className={`font-semibold ${c.passed ? 'text-green-700' : 'text-red-600'}`}>
                                  {c.passed ? '✅ Pass' : c.critical ? '🔴 Fail' : '🟡 Fail'}
                                </span>
                              </td>
                              <td className="px-4 py-2 text-slate-600">{formatValue(c.expected)}</td>
                              <td className="px-4 py-2 text-slate-600">{formatValue(c.actual)}</td>
                              <td className="px-4 py-2 text-slate-500">{c.difference != null ? c.difference.toLocaleString('en-IN') : '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                )}
              </>
            ) : (
              <Alert type="info">Math validation data not yet available for this session.</Alert>
            )}
          </Card>

          {/* Compliance flags — Agent 2 */}
          {session.anomaly_flags && session.anomaly_flags.length > 0 && (
            <Card>
              <SectionHeading>⚠️ Compliance Flags — Agent 2</SectionHeading>
              <div className="space-y-3">
                {session.anomaly_flags.map(f => (
                  <div key={f.rule_id} className={`rounded-xl border p-4 text-sm ${
                    f.severity === 'critical' ? 'border-red-200 bg-red-50' : 'border-yellow-200 bg-yellow-50'
                  }`}>
                    <div className="flex items-center gap-2 font-semibold">
                      <span>{f.severity === 'critical' ? '🔴' : '🟡'}</span>
                      <code className="text-xs">{f.rule_id}</code>
                      <span className="text-slate-600 font-normal">{f.description}</span>
                    </div>
                    {(f.expected || f.actual) && (
                      <div className="mt-2 flex gap-6 text-xs text-slate-500">
                        {f.expected && <span>Expected: <span className="font-medium text-slate-700">{f.expected}</span></span>}
                        {f.actual   && <span>Actual: <span className="font-medium text-slate-700">{f.actual}</span></span>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Field source audit trail */}
          <Card>
            <SectionHeading>📋 Field Source Audit Trail</SectionHeading>
            <div className="mb-4 grid grid-cols-3 gap-3">
              <div className="rounded-xl bg-green-50 p-3 text-center">
                <div className="text-2xl font-bold text-green-700">{fieldGroups.regex.length}</div>
                <div className="text-xs text-slate-500 mt-1">✅ Regex-extracted</div>
              </div>
              <div className="rounded-xl bg-amber-50 p-3 text-center">
                <div className="text-2xl font-bold text-amber-700">{fieldGroups.llm.length}</div>
                <div className="text-xs text-slate-500 mt-1">⚠️ LLM-extracted</div>
              </div>
              <div className="rounded-xl bg-blue-50 p-3 text-center">
                <div className="text-2xl font-bold text-blue-700">{fieldGroups.verified.length}</div>
                <div className="text-xs text-slate-500 mt-1">🔒 Auditor-verified</div>
              </div>
            </div>

            <div className="space-y-3">
              {fieldGroups.regex.length > 0 && (
                <details open>
                  <summary className="cursor-pointer rounded-xl bg-green-50 px-4 py-3 text-sm font-semibold text-green-800 hover:bg-green-100">
                    ✅ {fieldGroups.regex.length} regex-extracted fields — deterministic, no LLM
                  </summary>
                  <div className="mt-2"><FieldTable rows={fieldGroups.regex as [string,string][]} source="regex" /></div>
                </details>
              )}
              {fieldGroups.llm.length > 0 && (
                <details open>
                  <summary className="cursor-pointer rounded-xl bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800 hover:bg-amber-100">
                    ⚠️ {fieldGroups.llm.length} LLM-extracted fields — verify before finalising report
                  </summary>
                  <div className="mt-2"><FieldTable rows={fieldGroups.llm as [string,string][]} source="llm" /></div>
                </details>
              )}
              {fieldGroups.verified.length > 0 && (
                <details>
                  <summary className="cursor-pointer rounded-xl bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800 hover:bg-blue-100">
                    🔒 {fieldGroups.verified.length} auditor-verified fields
                  </summary>
                  <div className="mt-2"><FieldTable rows={fieldGroups.verified as [string,string][]} source="auditor_verified" /></div>
                </details>
              )}
              {fieldGroups.regex.length === 0 && fieldGroups.llm.length === 0 && (
                <Alert type="info">No source data yet — upload documents to see the field breakdown.</Alert>
              )}
            </div>
          </Card>

          {/* LLM audit observations */}
          {auditObs.length > 0 && (
            <Card>
              <SectionHeading>💡 Initial Audit Observations (LLM)</SectionHeading>
              <ul className="space-y-2 text-sm text-slate-700">
                {auditObs.map((obs, i) => (
                  <li key={i} className="flex gap-3 rounded-xl bg-slate-50 p-3">
                    <span className="text-indigo-500 mt-0.5">•</span>
                    <span>{obs}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <div className="flex justify-end gap-3">
            <button onClick={() => navigate('/verify')}
              className="rounded-full border border-indigo-300 px-5 py-2.5 text-sm font-semibold text-indigo-700 hover:bg-indigo-50">
              ✏️ Verify Fields First
            </button>
            <button onClick={() => navigate('/anomaly')}
              className="rounded-full bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">
              Proceed to Anomaly Detection →
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default Ingest
