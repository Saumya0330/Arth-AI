import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getFinancials, updateFinancials } from '../api/client'
import { Alert, Card, SourceBadge, Spinner } from '../components'

const SESSION_ID_KEY = 'arthAI_sessionId'
const SESSION_COMPANY_KEY = 'arthAI_sessionCompany'

type FinancialResponse = Awaited<ReturnType<typeof getFinancials>>

const sections: Array<{ title: string; fields: Array<[string, string]> }> = [
  {
    title: 'Company Info',
    fields: [
      ['Company Name', 'company_name'],
      ['CIN', 'cin'],
      ['PAN', 'pan'],
      ['Financial Year', 'financial_year_end'],
      ['Auditor Name', 'auditor_name'],
      ['Auditor Firm Reg.', 'auditor_firm_reg'],
    ],
  },
  {
    title: 'Balance Sheet Equity',
    fields: [
      ['Share Capital', 'balance_sheet.shareholders_equity.share_capital'],
      ['Reserves & Surplus', 'balance_sheet.shareholders_equity.reserves_and_surplus'],
      ['Share Warrants Money', 'balance_sheet.shareholders_equity.money_received_against_share_warrants'],
    ],
  },
  {
    title: 'BS Non-Current Liabilities',
    fields: [
      ['Long-Term Borrowings', 'balance_sheet.non_current_liabilities.long_term_borrowings'],
      ['Deferred Tax Liabilities', 'balance_sheet.non_current_liabilities.deferred_tax_liabilities'],
      ['Other Long-Term Liabilities', 'balance_sheet.non_current_liabilities.other_long_term_liabilities'],
      ['Long-Term Provisions', 'balance_sheet.non_current_liabilities.long_term_provisions'],
    ],
  },
  {
    title: 'BS Current Liabilities',
    fields: [
      ['Short-Term Borrowings', 'balance_sheet.current_liabilities.short_term_borrowings'],
      ['Trade Payables', 'balance_sheet.current_liabilities.trade_payables'],
      ['Other Current Liabilities', 'balance_sheet.current_liabilities.other_current_liabilities'],
      ['Short-Term Provisions', 'balance_sheet.current_liabilities.short_term_provisions'],
    ],
  },
  {
    title: 'BS Non-Current Assets',
    fields: [
      ['Tangible Fixed Assets', 'balance_sheet.non_current_assets.fixed_assets_tangible'],
      ['Intangible Assets', 'balance_sheet.non_current_assets.fixed_assets_intangible'],
      ['Capital WIP', 'balance_sheet.non_current_assets.capital_wip'],
      ['Long-Term Investments', 'balance_sheet.non_current_assets.long_term_investments'],
      ['Deferred Tax Assets', 'balance_sheet.non_current_assets.deferred_tax_assets'],
      ['Long-Term Loans & Advances', 'balance_sheet.non_current_assets.long_term_loans_and_advances'],
      ['Other Non-Current Assets', 'balance_sheet.non_current_assets.other_non_current_assets'],
    ],
  },
  {
    title: 'BS Current Assets',
    fields: [
      ['Inventories', 'balance_sheet.current_assets.inventories'],
      ['Trade Receivables', 'balance_sheet.current_assets.trade_receivables'],
      ['Cash & Cash Equivalents', 'balance_sheet.current_assets.cash_and_cash_equivalents'],
      ['Short-Term Loans & Advances', 'balance_sheet.current_assets.short_term_loans_and_advances'],
      ['Other Current Assets', 'balance_sheet.current_assets.other_current_assets'],
    ],
  },
  {
    title: 'P&L Statement',
    fields: [
      ['Revenue from Operations', 'profit_and_loss.revenue_from_operations'],
      ['Other Income', 'profit_and_loss.other_income'],
      ['Cost of Materials', 'profit_and_loss.cost_of_materials'],
      ['Employee Benefits Expense', 'profit_and_loss.employee_benefits_expense'],
      ['Finance Costs', 'profit_and_loss.finance_costs'],
      ['Depreciation', 'profit_and_loss.depreciation'],
      ['Other Expenses', 'profit_and_loss.other_expenses'],
      ['Exceptional Items', 'profit_and_loss.exceptional_items'],
      ['Tax Expense', 'profit_and_loss.tax_expense'],
      ['Profit After Tax', 'profit_and_loss.profit_after_tax'],
    ],
  },
]

const readValue = (record: Record<string, unknown> | undefined, path: string) => {
  return path.split('.').reduce<unknown>((accumulator, key) => {
    if (!accumulator || typeof accumulator !== 'object') return undefined
    return (accumulator as Record<string, unknown>)[key]
  }, record)
}

const normalizeValue = (value: unknown) => (value === null || value === undefined ? '' : String(value))

const VerifyFinancials = () => {
  const sessionId = localStorage.getItem(SESSION_ID_KEY)
  const [data, setData] = useState<FinancialResponse | null>(null)
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
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
        const response = await getFinancials(sessionId)
        if (!active) return
        setData(response)
        const nextValues = sections.flatMap(section => section.fields).reduce<Record<string, string>>((accumulator, [, path]) => {
          accumulator[path] = normalizeValue(readValue(response.financial_json as Record<string, unknown>, path))
          return accumulator
        }, {})
        setFormValues(nextValues)
        const companyName = normalizeValue(readValue(response.financial_json as Record<string, unknown>, 'company_name'))
        if (companyName) {
          localStorage.setItem(SESSION_COMPANY_KEY, companyName)
          window.dispatchEvent(new Event('arthai-session-change'))
        }
        setError(null)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Unable to load financial fields.')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [sessionId])

  const sourceSummary = useMemo(() => {
    const sources = data?.field_sources ?? {}
    return {
      regex: Object.values(sources).filter(source => source === 'regex').length,
      llm: Object.values(sources).filter(source => source === 'llm').length,
      verified: Object.values(sources).filter(source => source === 'auditor_verified').length,
    }
  }, [data])

  const changedFields = useMemo(() => {
    if (!data) return []
    return sections.flatMap(section => section.fields).reduce<string[]>((accumulator, [, path]) => {
      const original = normalizeValue(readValue(data.financial_json as Record<string, unknown>, path))
      if ((formValues[path] ?? '') !== original) accumulator.push(path)
      return accumulator
    }, [])
  }, [data, formValues])

  const saveChanges = async () => {
    if (!sessionId || changedFields.length === 0) return

    try {
      setSaving(true)
      const edits = changedFields.map(path => ({
        path,
        value: (formValues[path] ?? '').trim() === '' ? null : formValues[path],
      }))
      const response = await updateFinancials(sessionId, edits)
      const refreshed = await getFinancials(sessionId)
      setData(refreshed)
      const nextValues = sections.flatMap(section => section.fields).reduce<Record<string, string>>((accumulator, [, path]) => {
        accumulator[path] = normalizeValue(readValue(refreshed.financial_json as Record<string, unknown>, path))
        return accumulator
      }, {})
      setFormValues(nextValues)
      setSuccess(`Saved ${response.fields_updated.length} field(s). Total verified fields: ${response.auditor_verified_count}.`)
      setError(null)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save verified values.')
      setSuccess(null)
    } finally {
      setSaving(false)
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
      {loading && <Spinner text="Loading financial statement fields..." />}
      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      {!loading && data && (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="bg-slate-50">
              <div className="text-xs uppercase tracking-wide text-slate-500">Regex count</div>
              <div className="mt-2 text-3xl font-semibold text-green-700">{sourceSummary.regex}</div>
            </Card>
            <Card className="bg-slate-50">
              <div className="text-xs uppercase tracking-wide text-slate-500">LLM count</div>
              <div className="mt-2 text-3xl font-semibold text-amber-600">{sourceSummary.llm}</div>
            </Card>
            <Card className="bg-slate-50">
              <div className="text-xs uppercase tracking-wide text-slate-500">Verified count</div>
              <div className="mt-2 text-3xl font-semibold text-indigo-700">{sourceSummary.verified}</div>
            </Card>
          </div>

          {sections.map((section, index) => (
            <details key={section.title} open={index === 0} className="rounded-3xl border border-slate-200 bg-white shadow-sm">
              <summary className="cursor-pointer list-none px-6 py-5 text-lg font-semibold text-slate-900">{section.title}</summary>
              <div className="space-y-4 border-t border-slate-100 px-6 py-6">
                {section.fields.map(([label, path]) => {
                  const changed = changedFields.includes(path)
                  return (
                    <div key={path} className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)_10rem] lg:items-center">
                      <label htmlFor={path} className="text-sm font-medium text-slate-700">{label}</label>
                      <input
                        id={path}
                        value={formValues[path] ?? ''}
                        onChange={event => {
                          setFormValues(current => ({ ...current, [path]: event.target.value }))
                          setSuccess(null)
                        }}
                        className={[
                          'w-full rounded-2xl border px-4 py-3 text-sm outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100',
                          changed ? 'border-yellow-400 bg-yellow-50' : 'border-slate-200 bg-white',
                        ].join(' ')}
                      />
                      <div className="justify-self-start lg:justify-self-end">
                        <SourceBadge source={data.field_sources?.[path] ?? 'unknown'} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </details>
          ))}

          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-slate-500">Changed fields are highlighted in yellow and only modified values are sent to the API.</p>
            <button
              type="button"
              onClick={() => void saveChanges()}
              disabled={saving || changedFields.length === 0}
              className="rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Verified Values'}
            </button>
          </div>

          <div className="flex justify-end">
            <Link to="/report" className="rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700">
              Proceed to Report Generation →
            </Link>
          </div>
        </>
      )}
    </div>
  )
}

export default VerifyFinancials
