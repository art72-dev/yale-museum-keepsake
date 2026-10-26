import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, byline, type ObjectCard as Card, type ScanResponse } from '../api'
import { Painting } from '../components/Art'
import ObjectImage from '../components/ObjectImage'
import OwnPhotoControls from '../components/OwnPhotoControls'
import { useFavorites } from '../favorites'
import { toJpeg } from '../photo'

const WORKING = ['Reading the photo…', 'Looking through the collection…', 'Writing the page…', 'Adding it to your book…']

function Pick({ c, onPick }: { c: Card; onPick: (c: Card) => void }) {
  return (
    <article className="card pick">
      <Link to={`/object/${c.id}`} className="card-link">
        <ObjectImage id={c.id} title={c.title} usable={c.image_usable} rights={c.rights} />
        <div className="card-body">
          <h3>{c.title}</h3>
          <p className="byline">{byline(c)}</p>
          <p className="meta">{c.museum}{c.accession_number && ` · ${c.accession_number}`}</p>
        </div>
      </Link>
      <button className="btn btn-pink pick-btn" onClick={() => onPick(c)}>This one</button>
    </article>
  )
}

export default function Scan() {
  const { add, remove, refresh, ids } = useFavorites()
  const [photo, setPhoto] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tick, setTick] = useState(0)
  const [result, setResult] = useState<ScanResponse | null>(null)
  const [picked, setPicked] = useState<Card | null>(null)
  const [before, setBefore] = useState<string[]>([])       // the book before this scan, to tell new from already-saved
  const [error, setError] = useState('')
  const camera = useRef<HTMLInputElement>(null)
  const library = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!busy) return
    const t = setInterval(() => setTick((n) => Math.min(n + 1, WORKING.length - 1)), 2200)
    return () => clearInterval(t)
  }, [busy])

  const start = async (file: File | undefined) => {
    if (!file) return
    setError('')
    setResult(null)
    setPicked(null)
    setTick(0)
    setBefore(ids)
    try {
      const jpeg = await toJpeg(file)
      setPhoto(jpeg)
      setBusy(true)
      const r = await api.scan(jpeg)
      setResult(r)
      if (r.status === 'added') await refresh()          // the scanner added it on the server
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
      if (camera.current) camera.current.value = ''
      if (library.current) library.current.value = ''
    }
  }

  const choose = (c: Card) => {
    setBefore(ids)
    add(c.id)
    setPicked(c)
  }

  const reset = () => {
    setPhoto(null)
    setResult(null)
    setPicked(null)
    setError('')
  }

  const added = result?.status === 'added' ? result.object : picked
  const page = added ? ids.indexOf(added.id) + 1 : 0
  const already = !!added && before.includes(added.id)     // it was in the book before: nothing to undo

  return (
    <div className="scan-page">
      <div className="scan-intro">
        <div>
          <p className="eyebrow">Scan</p>
          <h1>Snap the label. We'll do the rest.</h1>
          <p className="lede">
            Take a photo of an artwork's wall label (best) or of the object itself. We'll find it in Yale's collection,
            write its page, and add it to your book.
          </p>
          <div className="scan-buttons">
            <button className="btn btn-pink big-btn" onClick={() => camera.current?.click()} disabled={busy}>📷 Take a photo</button>
            <button className="btn" onClick={() => library.current?.click()} disabled={busy}>Choose a photo</button>
          </div>
          <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => start(e.target.files?.[0])} />
          <input ref={library} type="file" accept="image/*" hidden onChange={(e) => start(e.target.files?.[0])} />
          <p className="muted small">Tip: the label's object number (like “1958.59”) gives the surest match.</p>
        </div>
        <div className="viewfinder" aria-hidden>
          {photo ? <img src={photo} alt="" /> : <Painting kind="abstract" />}
          <i className="vf tl" /><i className="vf tr" /><i className="vf bl" /><i className="vf br" />
          {(busy || !photo) && <span className="scanline" />}
        </div>
      </div>

      {busy && (
        <div className="scan-status" aria-live="polite">
          {WORKING.map((w, i) => (
            <span key={w} className={i < tick ? 'done' : i === tick ? 'now' : ''}>{i < tick ? '✓ ' : ''}{w}</span>
          ))}
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {result && !busy && (
        <section className={`scan-result ${result.status}`} aria-live="polite">
          {added ? (
            <>
              <p className="scan-msg">
                {already ? `“${added.title}” is already in your book.`
                  : picked ? `✓ Added “${picked.title}” to your book.` : `✓ ${result.message}`}
              </p>
              <div className="scan-added">
                <ObjectImage id={added.id} title={added.title} usable={added.image_usable} rights={added.rights} />
                <div>
                  <p className="page-pill">Page {page} of your book</p>
                  <h2>{added.title}</h2>
                  <p className="byline">{byline(added)}</p>
                  {!picked && result.blurb && (
                    <>
                      <h3 className="scan-headline">{result.blurb.headline}</h3>
                      <p>{result.blurb.blurb}</p>
                    </>
                  )}
                  {!added.image_usable && (
                    <OwnPhotoControls id={added.id} rights={added.rights === 'No image' ? 'the museum has no photograph' : added.rights}
                                      offer={photo} />
                  )}
                  <div className="scan-actions">
                    <Link className="btn btn-pink" to={`/object/${added.id}`}>Open its page</Link>
                    {!already && <button className="btn" onClick={() => { remove(added.id); reset() }}>Undo</button>}
                    <button className="btn" onClick={reset}>Scan another</button>
                    <Link className="btn" to="/book">My book</Link>
                  </div>
                </div>
              </div>
            </>
          ) : result.status === 'choose' ? (
            <>
              <p className="scan-msg">{result.message}</p>
              <div className="grid">
                {result.candidates.map((c) => <Pick key={c.id} c={c} onPick={choose} />)}
              </div>
              <button className="btn more" onClick={reset}>None of these: scan again</button>
            </>
          ) : (
            <>
              <p className="scan-msg">{result.message}</p>
              {result.reading?.title && (
                <p className="muted">
                  I read: “{result.reading.title}”{result.reading.maker && `, ${result.reading.maker}`}
                  {result.reading.object_number && ` (${result.reading.object_number})`}. While the app has a sample of
                  the collection, many objects aren't in it yet.
                </p>
              )}
              <div className="scan-actions">
                <button className="btn btn-pink" onClick={reset}>Try another photo</button>
                {result.reading?.title && (
                  <Link className="btn" to={`/museum/all?q=${encodeURIComponent(result.reading.title)}`}>Search by hand</Link>
                )}
              </div>
            </>
          )}

          {result.steps.length > 0 && (
            <details className="scan-trace">
              <summary>How it found this</summary>
              <ol>{result.steps.map((s, i) => <li key={i}><code>{s.tool}</code> {s.summary}</li>)}</ol>
            </details>
          )}
        </section>
      )}
    </div>
  )
}
