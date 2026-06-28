import { useEffect, useState, type FormEvent } from 'react'
import { listRulebook, searchRulebook, type RulebookDoc } from '../api/client'
import { Alert, Card, SectionHeading, Spinner } from '../components'

type RulebookResponse = Awaited<ReturnType<typeof listRulebook>>
type SearchResponse = Awaited<ReturnType<typeof searchRulebook>>

const pageRangeLabel = (doc: RulebookDoc) => {
  if (doc.page_range.min === null || doc.page_range.max === null) return 'Page range unavailable'
  return `Pages ${doc.page_range.min}–${doc.page_range.max}`
}

const Rulebook = () => {
  const [docs, setDocs] = useState<RulebookResponse | null>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResponse['results']>([])
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    const load = async () => {
      try {
        const response = await listRulebook()
        if (!active) return
        setDocs(response)
        setError(null)
      } catch (loadError) {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : 'Unable to load rulebook documents.')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [])

  const onSearch = async (event: FormEvent) => {
    event.preventDefault()
    if (!query.trim()) {
      setResults([])
      return
    }

    try {
      setSearching(true)
      const response = await searchRulebook(query.trim())
      setResults(response.results)
      setError(null)
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Unable to search the rulebook.')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="space-y-8">
      {loading && <Spinner text="Loading embedded rulebook documents..." />}
      {error && <Alert type="error">{error}</Alert>}

      {!loading && docs && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="bg-slate-50">
              <div className="text-xs uppercase tracking-wide text-slate-500">Total chunks</div>
              <div className="mt-2 text-3xl font-semibold text-slate-900">{docs.total_chunks}</div>
            </Card>
            <Card className="bg-slate-50">
              <div className="text-xs uppercase tracking-wide text-slate-500">Documents</div>
              <div className="mt-2 text-3xl font-semibold text-slate-900">{docs.documents.length}</div>
            </Card>
          </div>

          <Card>
            <SectionHeading>Embedded regulatory documents</SectionHeading>
            <div className="grid gap-4 lg:grid-cols-2">
              {docs.documents.map(doc => (
                <div key={doc.filename} className="rounded-3xl border border-slate-200 p-5">
                  <div className="text-lg font-semibold text-slate-900">{doc.filename}</div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-600">
                      <div className="text-xs uppercase tracking-wide text-slate-500">Chunks</div>
                      <div className="mt-2 font-semibold text-slate-900">{doc.chunk_count}</div>
                    </div>
                    <div className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-600">
                      <div className="text-xs uppercase tracking-wide text-slate-500">Pages</div>
                      <div className="mt-2 font-semibold text-slate-900">{doc.page_count}</div>
                    </div>
                    <div className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-600">
                      <div className="text-xs uppercase tracking-wide text-slate-500">Range</div>
                      <div className="mt-2 font-semibold text-slate-900">{pageRangeLabel(doc)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <SectionHeading>Search the rulebook</SectionHeading>
            <form onSubmit={event => void onSearch(event)} className="flex gap-3">
              <input
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="Search Companies Act, CARO, or SA guidance"
                className="flex-1 rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
              />
              <button type="submit" className="rounded-full bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700">
                Search
              </button>
            </form>

            {searching && <Spinner text="Searching regulatory chunks..." />}

            {!searching && results.length > 0 && (
              <div className="mt-6 space-y-4">
                {results.map((result: SearchResponse['results'][number]) => (
                  <div key={`${result.source}-${result.page}-${result.relevance_score}`} className="rounded-3xl border border-slate-200 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-sm font-semibold text-slate-900">{result.source}</div>
                      <div className="text-xs text-slate-500">Page {result.page} · Relevance {result.relevance_score.toFixed(3)}</div>
                    </div>
                    <p className="mt-4 text-sm leading-6 text-slate-700">{result.content}</p>
                  </div>
                ))}
              </div>
            )}

            {!searching && query.trim() && results.length === 0 && (
              <p className="mt-6 text-sm text-slate-500">No semantic matches found for this query.</p>
            )}
          </Card>
        </>
      )}
    </div>
  )
}

export default Rulebook
