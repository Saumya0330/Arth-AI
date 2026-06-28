import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSession, uploadPDF, type MathCheck, type PipelineState } from '../api/client'
import { Alert, Card, SectionHeading, SourceBadge, Spinner } from '../components'

const SESSION_ID_KEY = 'arthAI_sessionId'
const SESSION_COMPANY_KEY = 'arthAI_sessionCompany'
const STATUS_MESSAGES = ['Extracting text...', 'Running LLM...', 'Starting agents...']

type UploadSummary = Awaited<ReturnType<typeof uploadPDF>>

const getByPath = (record: Record<string, unknown> | undefined, path: string) => {
  return path.split('.').reduce<unknown>((accumulator, key) => {
    if (!accumulator || typeof accumulator !== 'object') return undefined
    return (accumulator as Record<string, unknown>)[key]
  }, record)
}

const formatPercent = (value: number | undefined) => `${Math.round((value || 0) * 100)}%`

const formatValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') return value.toLocaleString('en-IN')
  return String(value)
}

const Ingest = () => {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [statusIndex, setStatusIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ summary: UploadSummary; session: PipelineState } | null>(null)

  useEffect(() => {
    if (!uploading) return
    const timer = window.setInterval(() => {
      setStatusIndex(current => (current + 1) % STATUS_MESSAGES.length)
    }, 1400)
    return () => window.clearInterval(timer)
  }, [uploading])

  const fieldGroups = useMemo(() => {
    const sources = result?.session.field_sources ?? {}
    const entries = Object.entries(sources)
    return {
      regex: entries.filter(([, source]) => source === 'regex'),
      llm: entries.filter(([, source]) => source === 'llm'),
    }
  }, [result])

  const auditObservations = useMemo(() => {
    const observations = result?.session.financial_json?.audit_observations
    return Array.isArray(observations) ? observations : []
  }, [result])

  const handleFile = (file: File | null) => {
    if (!file) return
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are supported.')
      return
    }
    setSelectedFile(file)
    setError(null)
    setResult(null)
  }

  const saveSession = (sessionId: string, companyName?: string) => {
    localStorage.setItem(SESSION_ID_KEY, sessionId)
    if (companyName) localStorage.setItem(SESSION_COMPANY_KEY, companyName)
    window.dispatchEvent(new Event('arthai-session-change'))
  }

  const startUpload = async () => {
    if (!selectedFile) {
      setError('Select a PDF to begin.')
      return
    }

    try {
      setUploading(true)
      setStatusIndex(0)
      setError(null)
      const summary = await uploadPDF(selectedFile)
      const session = await getSession(summary.session_id)
      saveSession(summary.session_id, summary.company_name)
      setResult({ summary, session })
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const renderFieldTable = (rows: [string, string][], source: 'regex' | 'llm') => (
    <div className="overflow-hidden rounded-2xl border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">Field path</th>
            <th className="px-4 py-3 font-medium">Value</th>
            <th className="px-4 py-3 font-medium">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map(([path]) => (
            <tr key={path}>
              <td className="px-4 py-3 font-mono text-xs text-slate-600">{path}</td>
              <td className="px-4 py-3 text-slate-900">{formatValue(getByPath(result?.session.financial_json, path))}</td>
              <td className="px-4 py-3"><SourceBadge source={source} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  const companyInfo = result?.session.financial_json ?? {}
  const mathReport = result?.session.math_report
  const companyName = typeof companyInfo.company_name === 'string' ? companyInfo.company_name : result?.summary.company_name

  return (
    <div className="space-y-8">
      <Card>
        <SectionHeading>Upload audited financial statements</SectionHeading>
        <p className="mb-6 text-sm text-slate-500">Drop a PDF here or browse from disk. अर्थAI will extract text, complete financial fields, validate arithmetic, and prepare the anomaly queue.</p>

        <div
          onDragOver={event => {
            event.preventDefault()
            setDragActive(true)
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={event => {
            event.preventDefault()
            setDragActive(false)
            handleFile(event.dataTransfer.files[0] ?? null)
          }}
          onClick={() => inputRef.current?.click()}
          className={[
            'flex cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed px-8 py-14 text-center transition',
            dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 hover:border-indigo-300 hover:bg-slate-50',
          ].join(' ')}
        >
          <div className="text-4xl">📄</div>
          <h3 className="mt-4 text-xl font-semibold text-slate-900">Drag and drop your PDF</h3>
          <p className="mt-2 text-sm text-slate-500">PDF only · OCR and text-based statements supported</p>
          <button type="button" className="mt-6 rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700">
            Click to browse
          </button>
          {selectedFile && (
            <div className="mt-4 rounded-full bg-slate-100 px-4 py-2 text-sm text-slate-700">Selected: {selectedFile.name}</div>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={event => handleFile(event.target.files?.[0] ?? null)}
          />
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={() => void startUpload()}
            disabled={uploading || !selectedFile}
            className="rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Start audit ingestion
          </button>
        </div>
      </Card>

      {error && <Alert type="error">{error}</Alert>}

      {uploading && (
        <Card>
          <Spinner text={STATUS_MESSAGES[statusIndex]} />
          <p className="text-center text-sm text-slate-500">Large annual reports may take a minute while the extraction and agent pipeline completes.</p>
        </Card>
      )}

      {result && (
        <>
          <Card>
            <SectionHeading>Extraction results</SectionHeading>
            <div className="grid gap-4 lg:grid-cols-5">
              <div className="rounded-2xl bg-slate-50 p-4 lg:col-span-2">
                <div className="text-xs uppercase tracking-wide text-slate-500">Company</div>
                <div className="mt-2 text-xl font-semibold text-slate-900">{companyName || '—'}</div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-500">CIN</div>
                <div className="mt-2 text-base font-semibold text-slate-900">{formatValue(companyInfo.cin)}</div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-500">FY</div>
                <div className="mt-2 text-base font-semibold text-slate-900">{formatValue(companyInfo.financial_year_end)}</div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-500">Auditor</div>
                <div className="mt-2 text-base font-semibold text-slate-900">{formatValue(companyInfo.auditor_name)}</div>
              </div>
            </div>

            <div className="mt-6 rounded-2xl border border-slate-200 p-5">
              <div className="flex items-center justify-between gap-4 text-sm">
                <span className="font-medium text-slate-900">Extraction confidence</span>
                <span className="text-indigo-700">{formatPercent(result.summary.extraction_confidence)}</span>
              </div>
              <div className="mt-3 h-3 rounded-full bg-slate-100">
                <div
                  className="h-3 rounded-full bg-indigo-600 transition-all"
                  style={{ width: formatPercent(result.summary.extraction_confidence) }}
                />
              </div>
            </div>
          </Card>

          <Card>
            <SectionHeading>Math validation results (Agent 1)</SectionHeading>
            {mathReport?.checks?.length ? (
              <div className="overflow-hidden rounded-2xl border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-slate-500">
                    <tr>
                      <th className="px-4 py-3 font-medium">Check</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Expected</th>
                      <th className="px-4 py-3 font-medium">Actual</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {(mathReport.checks as MathCheck[]).map(check => (
                      <tr key={check.check}>
                        <td className="px-4 py-3 text-slate-900">{check.check}</td>
                        <td className="px-4 py-3">
                          <span className={check.passed ? 'font-medium text-green-700' : 'font-medium text-red-600'}>
                            {check.passed ? 'Pass' : 'Fail'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600">{formatValue(check.expected)}</td>
                        <td className="px-4 py-3 text-slate-600">{formatValue(check.actual)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Alert type="info">No math validation rows were returned for this extraction run.</Alert>
            )}
          </Card>

          <Card>
            <SectionHeading>Field source audit trail</SectionHeading>
            <div className="space-y-4">
              <details open className="rounded-2xl border border-green-200 bg-green-50 px-5 py-4">
                <summary className="cursor-pointer list-none text-sm font-semibold text-green-800">✅ Regex-extracted ({fieldGroups.regex.length} fields)</summary>
                <div className="mt-4">{renderFieldTable(fieldGroups.regex as [string, string][], 'regex')}</div>
              </details>

              <details open className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
                <summary className="cursor-pointer list-none text-sm font-semibold text-amber-800">⚠️ LLM-extracted ({fieldGroups.llm.length} fields, needs verification)</summary>
                <div className="mt-4">{renderFieldTable(fieldGroups.llm as [string, string][], 'llm')}</div>
              </details>
            </div>
          </Card>

          <Card>
            <SectionHeading>Audit observations from LLM</SectionHeading>
            {auditObservations.length > 0 ? (
              <ul className="space-y-3 text-sm text-slate-700">
                {auditObservations.map(observation => (
                  <li key={observation} className="flex gap-3 rounded-2xl bg-slate-50 p-4">
                    <span className="text-indigo-600">•</span>
                    <span>{observation}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Alert type="info">No audit observations were returned for this upload.</Alert>
            )}
          </Card>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => navigate('/anomaly')}
              className="rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              Proceed to Anomaly Detection →
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default Ingest
