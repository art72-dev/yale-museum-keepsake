import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, byline, type ObjectCard, type ObjectDetail } from '../api'
import { Mobile } from '../components/Art'
import ObjectImage from '../components/ObjectImage'
import { useFavorites } from '../favorites'
import { useOwnPhotos } from '../ownPhotos'

export default function MyBook() {
  const { ids, add, move, remove, clear, book, setBook } = useFavorites()
  const { photos, clearAll } = useOwnPhotos()
  const [objects, setObjects] = useState<Record<string, ObjectDetail>>({})
  const [mine, setMine] = useState<ObjectCard[]>([])        // objects this visitor added themselves

  useEffect(() => {
    api.addedList().then(setMine).catch(() => undefined)
  }, [])
  const setAside = mine.filter((m) => !ids.includes(m.id))

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
          <p className="scan-actions">
            <Link className="btn btn-pink" to="/">Browse the museums</Link>
            <Link className="btn" to="/add">+ Add an object yourself</Link>
          </p>
          <SetAside items={setAside} add={add} />
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
                {o?.added_by_visitor && <span className="added-tag small">Added by you</span>}
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

      <p className="muted add-line">Something you saw isn't in the app? <Link to="/add">Add it yourself</Link>: only you
        will see it, and its page says the details came from you.</p>
      <SetAside items={setAside} add={add} />

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

/** Objects the visitor added and later took out of the book: one tap puts them back. */
function SetAside({ items, add }: { items: ObjectCard[]; add: (id: string) => void }) {
  if (items.length === 0) return null
  return (
    <div className="set-aside">
      <p className="muted">You added these, but they aren't in your book now:</p>
      <ul>
        {items.map((m) => (
          <li key={m.id}>
            <Link to={`/object/${m.id}`}>{m.title}</Link> <span className="muted">{byline(m)}</span>{' '}
            <button className="linkish" onClick={() => add(m.id)}>Put back</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
