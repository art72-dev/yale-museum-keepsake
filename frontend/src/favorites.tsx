// The visitor's saved objects and book settings. Saved objects are kept in this browser and synced to the
// server (under a random visitor ID, no account), so the scanner's add_to_book tool can add pages too.
// The book's title and the visitor's name stay in this browser only.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'

type Book = { title: string; owner: string }

type Favorites = {
  ids: string[]
  isSaved: (id: string) => boolean
  toggle: (id: string) => void
  add: (id: string) => void
  refresh: () => Promise<void>
  move: (id: string, delta: number) => void
  remove: (id: string) => void
  clear: () => void
  book: Book
  setBook: (b: Book) => void
}

const Ctx = createContext<Favorites | null>(null)

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<string[]>(() => load('keepsake.favorites', []))
  const [book, setBook] = useState<Book>(() => load('keepsake.book', { title: 'My Yale Museum Keepsake', owner: '' }))

  const [synced, setSynced] = useState(false)

  useEffect(() => localStorage.setItem('keepsake.favorites', JSON.stringify(ids)), [ids])

  // First load: merge what the server has (e.g. pages the scanner added) with this browser's list.
  useEffect(() => {
    api.getBook()
      .then((server) => setIds((cur) => [...cur, ...server.filter((id) => !cur.includes(id))]))
      .catch(() => undefined)
      .finally(() => setSynced(true))
  }, [])

  // After that, every change is sent to the server (a moment later, so quick edits go as one).
  useEffect(() => {
    if (!synced) return
    const t = setTimeout(() => api.putBook(ids).catch(() => undefined), 300)
    return () => clearTimeout(t)
  }, [ids, synced])

  const refresh = useCallback(async () => {
    try {
      setIds(await api.getBook())
    } catch {
      /* keep the local list */
    }
  }, [])
  useEffect(() => localStorage.setItem('keepsake.book', JSON.stringify(book)), [book])

  const value: Favorites = {
    ids,
    isSaved: (id) => ids.includes(id),
    toggle: (id) => setIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id])),
    add: (id) => setIds((cur) => (cur.includes(id) ? cur : [...cur, id])),
    refresh,
    move: (id, delta) =>
      setIds((cur) => {
        const i = cur.indexOf(id)
        const j = i + delta
        if (i < 0 || j < 0 || j >= cur.length) return cur
        const next = [...cur]
        ;[next[i], next[j]] = [next[j], next[i]]
        return next
      }),
    remove: (id) => setIds((cur) => cur.filter((x) => x !== id)),
    clear: () => setIds([]),
    book,
    setBook,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useFavorites(): Favorites {
  const v = useContext(Ctx)
  if (!v) throw new Error('useFavorites must be inside FavoritesProvider')
  return v
}
