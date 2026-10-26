import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, cleanMaker, makerDetail, OPEN_ACCESS, OPEN_ACCESS_URL, type Blurb, type ObjectDetail } from '../api'
import { Bust } from '../components/Art'
import ObjectImage from '../components/ObjectImage'
import OwnPhotoControls from '../components/OwnPhotoControls'
import SaveButton from '../components/SaveButton'

export function Facts({ o }: { o: ObjectDetail }) {
  const maker = makerDetail(o.creators_display || o.maker)
  const rows: [string, string][] = [
    ['Maker', maker],
    ['Collected by', maker ? '' : cleanMaker(o.collectors)],
    [o.date_kind === 'collected' ? 'Collected' : 'Date', o.date],
    ['Type', o.type],
    ['Medium', o.medium],
    ['Dimensions', o.dimensions],
    ['Culture', o.culture],
    ['Period', o.period],
    ['Museum', o.museum],
    ['Department', o.department],
    ['Object number', o.accession_number],
    ['Credit', o.credit_line],
  ]
  return (
    <dl className="facts">
      {rows.filter(([, v]) => v).map(([k, v]) => (
        <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
      ))}
    </dl>
  )
}

export default function ObjectPage() {
  const { id = '' } = useParams()
  const [o, setO] = useState<ObjectDetail | null>(null)
  const [blurb, setBlurb] = useState<Blurb | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setO(null)
    setBlurb(null)
    setError('')
    api.object(id).then(setO).catch((e) => setError(String(e)))
    api.blurb(id).then(setBlurb).catch(() => setBlurb(null))
    window.scrollTo(0, 0)
  }, [id])

  if (error) return <p className="error">Couldn't load this object: {error}</p>
  if (!o) return <p className="muted">Loading…</p>

  return (
    <div className="object-page">
      <p className="crumbs">
        <Link to="/">Museums</Link> / <Link to={`/museum/${o.museum_slug}`}>{o.museum}</Link> /{' '}
        <Link to={`/museum/${o.museum_slug}?dept=${encodeURIComponent(o.department)}`}>{o.department}</Link>
      </p>
      <div className="object-layout">
        <div className="object-media">
          <ObjectImage id={o.id} title={o.title} usable={o.image_usable} rights={o.rights} size="large"
                       alt={o.alt_text} museumUrl={o.museum_page_url} />
          {o.image_usable && (
            <p className="img-credit">
              Image: {o.museum},{' '}
              {o.rights === OPEN_ACCESS ? (
                <>public domain (made before 1900), used under{' '}
                  <a href={OPEN_ACCESS_URL} target="_blank" rel="noreferrer">Yale's Open Access policy</a></>
              ) : o.rights}
            </p>
          )}
          {!o.image_usable && o.rights !== 'No image' && <OwnPhotoControls id={o.id} rights={o.rights} />}
          {!o.image_usable && o.rights === 'No image' && <OwnPhotoControls id={o.id} rights="the museum has no photograph" />}
        </div>
        <div className="object-text">
          <h1>{o.title}</h1>
          <SaveButton id={o.id} big />

          <section className="blurb-panel" aria-live="polite">
            {!blurb && (
              <div className="writing"><Bust /><p className="muted shimmer">Writing a short description from the museum's records…</p></div>
            )}
            {blurb && (
              <>
                <h2>{blurb.headline}</h2>
                <p>{blurb.blurb}</p>
                {blurb.look_closer && <p className="look-closer"><b>Look closer:</b> {blurb.look_closer}</p>}
                <p className="blurb-source">
                  {blurb.source === 'fallback'
                    ? blurb.note
                    : `Written by AI (${blurb.model}) using only this museum's records.`}
                </p>
              </>
            )}
          </section>

          <Facts o={o} />

          <p className="links">
            {o.museum_page_url && <a href={o.museum_page_url} target="_blank" rel="noreferrer">Museum page ↗</a>}
            <a href={o.lux_url} target="_blank" rel="noreferrer">LUX record ↗</a>
          </p>
        </div>
      </div>

      {o.related.length > 0 && (
        <section className="related">
          <h2 className="section-title">More from {o.related[0].why === 'same maker' ? 'this maker' : o.department}</h2>
          <ul>
            {o.related.map((r) => (
              <li key={r.id}><Link to={`/object/${r.id}`}>{r.title}</Link> <span className="muted">{cleanMaker(r.maker)} {r.date}</span></li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
