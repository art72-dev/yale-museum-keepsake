import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, byline, imageUrl, OPEN_ACCESS, type Blurb, type ObjectDetail } from '../api'
import { useFavorites } from '../favorites'
import { useOwnPhotos } from '../ownPhotos'

type Page = { o: ObjectDetail; b: Blurb | null }

// Fetch details + blurbs a few at a time (blurbs may need the AI writer; most come from the cache).
async function loadPages(ids: string[], onProgress: (n: number) => void): Promise<Page[]> {
  const pages: (Page | null)[] = new Array(ids.length).fill(null)
  let next = 0
  let done = 0
  async function worker() {
    while (next < ids.length) {
      const i = next++
      try {
        const [o, b] = await Promise.all([api.object(ids[i]), api.blurb(ids[i]).catch(() => null)])
        pages[i] = { o, b }
      } catch {
        pages[i] = null
      }
      onProgress(++done)
    }
  }
  await Promise.all([worker(), worker(), worker()])
  return pages.filter((p): p is Page => p !== null)
}

export default function PrintBook() {
  const { ids, book } = useFavorites()
  const { photos } = useOwnPhotos()
  const [pages, setPages] = useState<Page[] | null>(null)
  const [progress, setProgress] = useState(0)
  const [imagesLeft, setImagesLeft] = useState(0)
  const stack = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let live = true
    setPages(null)
    setProgress(0)
    loadPages(ids, (n) => live && setProgress(n)).then((p) => live && setPages(p))
    return () => {
      live = false
    }
  }, [ids])

  // Print only once every picture has arrived (checked directly, so cached images count too).
  useEffect(() => {
    if (!pages) return
    const check = () => {
      const imgs = [...(stack.current?.querySelectorAll('img') ?? [])]
      setImagesLeft(imgs.filter((i) => !i.complete).length)
    }
    check()
    const t = setInterval(check, 400)
    return () => clearInterval(t)
  }, [pages])

  const museums = useMemo(() => [...new Set(pages?.map((p) => p.o.museum) ?? [])], [pages])
  const museumList = new Intl.ListFormat('en', { type: 'conjunction' }).format(museums)
  const models = useMemo(() => [...new Set(pages?.map((p) => p.b?.model).filter(Boolean) ?? [])], [pages])
  const today = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })

  if (ids.length === 0) {
    return <div className="my-book"><p className="lede">Your book is empty. <Link to="/">Save some objects first.</Link></p></div>
  }

  const ready = pages !== null && imagesLeft === 0

  return (
    <div className="print-book">
      <div className="print-toolbar no-print">
        <Link to="/book">← Back to my book</Link>
        <span className="muted">
          {pages === null
            ? `Preparing pages… ${progress} of ${ids.length}`
            : imagesLeft > 0 ? `Loading images… ${imagesLeft} left` : `${pages.length + 2} pages ready`}
        </span>
        <button className="btn btn-pink" disabled={!ready} onClick={() => window.print()}>Print or save as PDF</button>
      </div>

      {pages && (
        <div className="paper-stack" ref={stack}>
          <section className="paper cover">
            <p className="cover-eyebrow">A keepsake from Yale's museums</p>
            <h1>{book.title || 'My Yale Museum Keepsake'}</h1>
            {book.owner && <p className="cover-owner">Chosen by {book.owner}</p>}
            <p className="cover-date">{today}</p>
            <div className="cover-strip">
              {pages.filter((p) => p.o.image_usable || photos[p.o.id]).slice(0, 4).map((p) => (
                <img key={p.o.id} src={p.o.image_usable ? imageUrl(p.o.id) : photos[p.o.id].dataUrl} alt="" />
              ))}
            </div>
            <p className="cover-museums">{museums.join(' · ')}</p>
          </section>

          {pages.map(({ o, b }, i) => (
            <section className="paper object-sheet" key={o.id}>
              <div className="sheet-image">
                {o.image_usable ? (
                  <img src={imageUrl(o.id, 'large')} alt={o.alt_text || o.title} />
                ) : photos[o.id] ? (
                  <figure className="sheet-own">
                    <img src={photos[o.id].dataUrl} alt={`Your photo of ${o.title}`} />
                    <figcaption>Your photo, taken at {o.museum}</figcaption>
                  </figure>
                ) : (
                  <div className="sheet-noimage">
                    <p>The museum's photograph can't be reproduced here.<br />Image rights: {o.rights}.</p>
                    {o.museum_page_url && <p>See it at <span className="url">{o.museum_page_url}</span></p>}
                  </div>
                )}
              </div>
              <div className="sheet-text">
                <p className="sheet-no">{i + 1}</p>
                <h2>{o.title}</h2>
                <p className="sheet-byline">{byline(o)}</p>
                {b && b.source !== 'fallback' && <h3>{b.headline}</h3>}
                {b && <p className="sheet-blurb">{b.blurb}</p>}
                {b?.look_closer && <p className="sheet-look"><b>Look closer:</b> {b.look_closer}</p>}
                <p className="sheet-details">
                  {[o.medium, o.dimensions].filter(Boolean).join('. ')}
                </p>
                <p className="sheet-credit">
                  {o.museum.includes(o.department) ? o.museum : `${o.museum}, ${o.department}`}
                  {o.accession_number && ` · ${o.accession_number}`}
                  {o.credit_line && <><br />{o.credit_line}</>}
                  {o.image_usable && <><br />Image: {o.museum}, {o.rights === OPEN_ACCESS
                    ? "public domain (made before 1900), used under Yale's Open Access policy" : o.rights}</>}
                  {!o.image_usable && photos[o.id] && <><br />Image: your own photo, for personal use. The museum's image
                    isn't cleared for reuse ({o.rights}).</>}
                </p>
              </div>
            </section>
          ))}

          <section className="paper colophon">
            <h2>About this book</h2>
            <p>
              The objects, their details and their photographs come from the collections of {museumList}, through
              Yale's LUX collections platform (lux.collections.yale.edu).
            </p>
            <p>
              Photographs are included only where the museum marks them public domain or CC0, or, for Yale University
              Library objects made before 1900, under Yale's Open Access policy for works in the public domain
              (guides.library.yale.edu/openaccess). Where the museum's image isn't cleared, the page shows the
              visitor's own photo, marked "Your photo", or a link to the museum's own page.
            </p>
            <p>
              Each description was written by an AI model{models.length ? ` (${models.join(', ')})` : ''} using only
              the museum's own records for that object, then checked so that every date, number and name appears in
              those records. Where the AI text wasn't available, the page shows the museum's details instead.
            </p>
            <p className="muted-print">Made with Yale Museum Keepsake, {today}.</p>
          </section>
        </div>
      )}
    </div>
  )
}
