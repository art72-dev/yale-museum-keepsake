import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, type MuseumSummary, type SearchPage } from '../api'
import { MUSEUM_ACCENT, MuseumEmblem } from '../components/Art'
import ObjectCard from '../components/ObjectCard'

// Words for the kinds of look-alike objects folded away while browsing ("undet." = undetermined specimen)
const KIND_LABEL: Record<string, string> = { undet: 'undetermined specimen', undetermined: 'undetermined specimen' }

export default function Browse() {
  const { slug = 'all' } = useParams()
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const printable = params.get('printable') === '1'
  const department = params.get('dept') ?? ''
  const [draft, setDraft] = useState(q)
  const [museum, setMuseum] = useState<MuseumSummary | null>(null)
  const [results, setResults] = useState<SearchPage | null>(null)
  const [items, setItems] = useState<SearchPage['items']>([])
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')

  useEffect(() => setDraft(q), [q])

  useEffect(() => {
    if (slug === 'all') return setMuseum(null)
    api.museums().then((ms) => setMuseum(ms.find((m) => m.slug === slug) ?? null)).catch(() => setMuseum(null))
  }, [slug])

  useEffect(() => {
    setPage(1)
  }, [slug, q, printable, department])

  useEffect(() => {
    let live = true
    setError('')
    api.search({ museum: slug, q, printable, department: department || undefined, page })
      .then((r) => {
        if (!live) return
        setResults(r)
        setItems((cur) => (page === 1 ? r.items : [...cur, ...r.items]))
      })
      .catch((e) => live && setError(String(e)))
    return () => {
      live = false
    }
  }, [slug, q, printable, department, page])

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    set('q', draft.trim())
  }

  const title = slug === 'all' ? 'All museums' : museum?.name ?? '…'

  return (
    <div className="browse" style={{ '--accent': MUSEUM_ACCENT[slug] ?? 'var(--rose)' } as CSSProperties}>
      <p className="crumbs"><Link to="/">Museums</Link> / {title}</p>
      <div className="browse-head">
        {slug !== 'all' && (
          <div className="emblem-tile" style={{ '--accent': MUSEUM_ACCENT[slug] ?? 'var(--rose)' } as CSSProperties}>
            <MuseumEmblem slug={slug} />
          </div>
        )}
        <div>
          <h1>{title}</h1>
          {museum?.info?.tagline && <p className="tagline">{museum.info.tagline}</p>}
        </div>
      </div>

      {museum?.info && (
        <section className="museum-about">
          <p className="about-blurb">{museum.info.blurb}</p>
          {museum.info.status && <p className="about-status">⚠︎ {museum.info.status}</p>}
          <ul className="about-facts">
            {museum.info.address && <li><span>📍</span>{museum.info.address}</li>}
            {museum.info.admission && <li><span>🎟</span>{museum.info.admission}</li>}
            <li><span>🖼</span>In this app: {museum.objects.toLocaleString()} objects, {museum.printable_images.toLocaleString()} with printable pictures</li>
          </ul>
          {museum.info.hours.length > 0 && (
            <div className="hours">
              <h3>Opening hours</h3>
              <div className="hours-groups">
                {museum.info.hours.map((g) => (
                  <table key={g.place || 'hours'} className="hours-table">
                    {g.place && <caption>{g.place}</caption>}
                    <tbody>
                      {g.rows.map((r) => (
                        <tr key={r.days} className={r.time === 'Closed' ? 'closed' : ''}><th>{r.days}</th><td>{r.time}</td></tr>
                      ))}
                    </tbody>
                  </table>
                ))}
              </div>
              {museum.info.hours_note && <p className="hours-note">{museum.info.hours_note}</p>}
              <p className="hours-source">
                From the <a href={museum.info.hours_source} target="_blank" rel="noreferrer">museum's website</a>, checked{' '}
                {new Date(museum.info.hours_checked + 'T12:00:00').toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })}.
                Holiday closures vary.
              </p>
            </div>
          )}
          <a className="about-link" href={museum.info.website} target="_blank" rel="noreferrer">Visit the museum's website ↗</a>
        </section>
      )}

      <form className="search" onSubmit={submit} role="search">
        <input value={draft} onChange={(e) => setDraft(e.target.value)}
               placeholder="Title, artist, material, or object number" aria-label="Search" />
        <button type="submit">Search</button>
      </form>

      <div className="filters">
        <label className={`chip ${printable ? 'on' : ''}`}>
          <input type="checkbox" checked={printable} onChange={(e) => set('printable', e.target.checked ? '1' : '')} />
          Printable images only
        </label>
        {museum && museum.departments.length > 1 && (
          <select value={department} onChange={(e) => set('dept', e.target.value)} aria-label="Department">
            <option value="">All departments</option>
            {museum.departments.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {results && (
        <p className="muted count">
          {results.total.toLocaleString()} {results.total === 1 ? 'object' : 'objects'}
          {q && <> matching “{q}”</>}
        </p>
      )}
      {results && results.hidden.length > 0 && (
        <p className="lookalikes">
          Showing a few of each kind. Also here:{' '}
          {results.hidden.map((h, i) => (
            <span key={`${h.department}-${h.kind}`}>
              {i > 0 && ', '}
              <button className="linkish" onClick={() => set('dept', h.department)}>
                {h.count} more {KIND_LABEL[h.kind] ?? h.kind}{h.count === 1 ? '' : 's'} in {h.department}
              </button>
            </span>
          ))}
        </p>
      )}
      {results && results.total === 0 && (
        <p className="empty">Nothing here yet. Try another word, or turn off a filter.</p>
      )}

      <div className="grid">
        {items.map((o) => <ObjectCard key={o.id} o={o} />)}
      </div>

      {results && items.length < results.total && (
        <button className="btn more" onClick={() => setPage((p) => p + 1)}>Show more</button>
      )}
    </div>
  )
}
