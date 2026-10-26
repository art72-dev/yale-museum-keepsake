import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type MuseumSummary } from '../api'
import { GalleryScene, MUSEUM_ACCENT, MuseumEmblem } from '../components/Art'
import { useFavorites } from '../favorites'

export default function Home() {
  const [museums, setMuseums] = useState<MuseumSummary[] | null>(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const { ids } = useFavorites()
  const navigate = useNavigate()

  useEffect(() => {
    api.museums().then(setMuseums).catch((e) => setError(String(e)))
  }, [])

  const search = (e: FormEvent) => {
    e.preventDefault()
    navigate(`/museum/all?q=${encodeURIComponent(q.trim())}`)
  }

  return (
    <div className="home">
      <section className="hero">
        <div>
          <p className="eyebrow">Yale's museums, in a book of your own</p>
          <h1><span className="c1">Save</span> what stops you.<br />Take it <span className="c2">home</span> in print.</h1>
          <p className="lede">
            As you walk the galleries, save the paintings, instruments, fossils and tablets you love. Each one gets a
            short, true description written from the museum's own records, and your favorites become a book you can print.
          </p>
          <form className="search big-search" onSubmit={search} role="search">
            <input value={q} onChange={(e) => setQ(e.target.value)}
                   placeholder="Search by title, artist, or the object number on the label" aria-label="Search all museums" />
            <button type="submit">Search</button>
          </form>
          <p className="scan-cta">
            <Link className="btn btn-pink" to="/scan">📷 Scan an artwork</Link>
            <span className="muted">Snap a wall label and it's added to your book. Not in the app?{' '}
              <Link to="/add">Add it yourself</Link>.</span>
          </p>
          <ul className="steps">
            <li><b>Save</b> objects as you go</li>
            <li><b>Read</b> a short description of each</li>
            <li><b>Print</b> your keepsake book</li>
          </ul>
          {ids.length > 0 && (
            <Link className="btn btn-pink" to="/book">Open my book ({ids.length} saved)</Link>
          )}
        </div>
        <GalleryScene />
      </section>

      <section>
        <h2 className="section-title">Choose a museum</h2>
        {error && <p className="error">Couldn't load the museums: {error}. Is the backend running?</p>}
        {!museums && !error && <p className="muted">Loading…</p>}
        <div className="museum-grid">
          {museums?.map((m) => (
            <Link key={m.slug} to={`/museum/${m.slug}`} className="museum-card"
                  style={{ '--accent': MUSEUM_ACCENT[m.slug] ?? 'var(--rose)' } as CSSProperties}>
              <div className="emblem-tile"><MuseumEmblem slug={m.slug} /></div>
              <div>
                <h3>{m.name}</h3>
                {m.info?.tagline && <p className="card-tagline">{m.info.tagline}</p>}
                <p className="meta">
                  {m.objects.toLocaleString()} objects · {m.printable_images.toLocaleString()} with printable images
                </p>
                {m.info?.hours_summary && <p className="card-hours">🕰 {m.info.hours_summary}</p>}
                <p className="depts">{m.departments.slice(0, 4).join(' · ')}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
