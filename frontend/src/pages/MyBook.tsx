import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, byline, type ObjectDetail } from '../api'
import { Mobile } from '../components/Art'
import ObjectImage from '../components/ObjectImage'
import { useFavorites } from '../favorites'
import { useOwnPhotos } from '../ownPhotos'

export default function MyBook() {
  const { ids, move, remove, clear, book, setBook } = useFavorites()
  const { photos, clearAll } = useOwnPhotos()
  const [objects, setObjects] = useState<Record<string, ObjectDetail>>({})

  useEffect(() => {
    ids.filter((id) => !objects[id]).forEach((id) =>
      api.object(id).then((o) => setObjects((cur) => ({ ...cur, [id]: o }))).catch(() => undefined))
  }, [ids]) // eslint-disable-line react-hooks/exhaustive-deps

  if (ids.length === 0) {
    return (
      <div className="my-book empty-book">
        <div>
          <h1>My book</h1>
          <p className="lede">Nothing saved yet. Tap ♡ on anything you like and it will appear here, ready to print.</p>
          <Link className="btn btn-pink" to="/">Browse the museums</Link>
        </div>
        <Mobile />
      </div>
    )
  }

  const printable = ids.filter((id) => objects[id]?.image_usable || photos[id]).length
  const own = ids.filter((id) => photos[id] && objects[id] && !objects[id].image_usable).length

  return (
    <div className="my-book">
      <h1>My book</h1>
      <div className="book-settings">
        <label>Book title
          <input value={book.title} maxLength={80} onChange={(e) => setBook({ ...book, title: e.target.value })} />
        </label>
        <label>Made by (optional)
          <input value={book.owner} maxLength={60} placeholder="Your name"
                 onChange={(e) => setBook({ ...book, owner: e.target.value })} />
        </label>
      </div>
      <p className="muted">
        {ids.length} {ids.length === 1 ? 'page' : 'pages'} · {printable} with pictures{own > 0 && ` (${own} your own photo${own === 1 ? '' : 's'})`}.
        Pages print in this order. Open a page without a picture to add your own photo.
      </p>

      <ol className="book-list">
        {ids.map((id, i) => {
          const o = objects[id]
          return (
            <li key={id}>
              <span className="page-no">{i + 1}</span>
              {o ? (
                <ObjectImage id={o.id} title={o.title} usable={o.image_usable} rights={o.rights} />
              ) : <div className="obj-img img-placeholder" />}
              <div className="book-item-text">
                {o ? <Link to={`/object/${id}`}><b>{o.title}</b></Link> : <b>Loading…</b>}
                {o && <span className="muted">{byline(o)} · {o.museum}</span>}
              </div>
              <div className="book-item-actions">
                <button onClick={() => move(id, -1)} disabled={i === 0} aria-label="Move up">↑</button>
                <button onClick={() => move(id, 1)} disabled={i === ids.length - 1} aria-label="Move down">↓</button>
                <button onClick={() => remove(id)} aria-label="Remove">Remove</button>
              </div>
            </li>
          )
        })}
      </ol>

      <div className="book-actions">
        <Link className="btn btn-pink" to="/book/print">Preview and print my book</Link>
        <button className="btn" onClick={() => {
          if (window.confirm('Remove every saved object and your photos?')) {
            clear()
            clearAll()
          }
        }}>Start over</button>
      </div>
    </div>
  )
}
