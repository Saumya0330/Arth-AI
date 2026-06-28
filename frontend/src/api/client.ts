// अर्थAI — API Client
// All API calls go through here. Never call fetch() directly in components.

import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ── Types ──────────────────────────────────────────────────────────────────────

export interface Session {
  session_id: string
  company_name: string
  financial_year: string
  extraction_confidence: number
  pipeline_step: string
}

export interface MathCheck {
  check: string
  passed: boolean
  critical: boolean
  expected?: number
  actual?: number
  difference?: number
  note?: string
}

export interface AnomalyFlag {
  rule_id: string
  severity: 'critical' | 'warning' | 'info'
  field: string
  description: string
  expected?: string
  actual?: string
  regulatory_passages?: { source: string; page: number; relevance_score: number; content: string }[]
  regulatory_response?: string
}

export interface PipelineState {
  current_step: string
  _next_nodes: string[]
  financial_json?: Record<string, unknown>
  field_sources?: Record<string, string>
  math_report?: { total_checks: number; passed: number; failed: number; has_critical_errors: boolean; checks: MathCheck[] }
  anomaly_flags?: AnomalyFlag[]
  flags_with_citations?: AnomalyFlag[]
  report_sections?: Record<string, unknown>
  report_markdown?: string
  report_finalised?: boolean
}

export interface RulebookDoc {
  filename: string
  chunk_count: number
  page_count: number
  page_range: { min: number | null; max: number | null }
}

// ── Sessions ───────────────────────────────────────────────────────────────────

export const uploadPDF = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/sessions/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const listSessions = (): Promise<Session[]> =>
  api.get('/sessions').then(r => r.data)

export const getSession = (id: string): Promise<PipelineState> =>
  api.get(`/sessions/${id}`).then(r => r.data)

// ── Pipeline ───────────────────────────────────────────────────────────────────

export interface FlagDecision {
  rule_id: string
  decision: 'confirm' | 'dismiss' | 'escalate'
  note?: string
}

export const reviewFlags = (id: string, decisions: FlagDecision[]) =>
  api.post(`/pipeline/${id}/flags/review`, { decisions }).then(r => r.data)

export interface FinaliseRequest {
  edits: Record<string, string>
  auditor_name?: string
  firm_name?: string
  firm_reg?: string
  membership_no?: string
  place?: string
  sign_date?: string
}

export const finaliseReport = (id: string, body: FinaliseRequest) =>
  api.post(`/pipeline/${id}/report/finalise`, body).then(r => r.data)

// ── Financials ─────────────────────────────────────────────────────────────────

export const getFinancials = (id: string) =>
  api.get(`/financials/${id}`).then(r => r.data)

export const updateFinancials = (id: string, edits: { path: string; value: unknown }[]) =>
  api.put(`/financials/${id}`, { edits }).then(r => r.data)

// ── Report ─────────────────────────────────────────────────────────────────────

export const getReport = (id: string) =>
  api.get(`/report/${id}`).then(r => r.data)

export const downloadReport = (id: string) =>
  window.open(`/api/report/${id}/download`, '_blank')

// ── Chat & Rulebook ────────────────────────────────────────────────────────────

export const chatQuery = (question: string, top_k = 4) =>
  api.post('/chat', { question, top_k }).then(r => r.data)

export const listRulebook = (): Promise<{ total_chunks: number; documents: RulebookDoc[] }> =>
  api.get('/rulebook').then(r => r.data)

export const searchRulebook = (query: string, top_k = 5) =>
  api.post('/rulebook/search', { query, top_k }).then(r => r.data)
