// The visitor's own photos of works whose museum image can't be printed. Kept only in this browser
// (IndexedDB); never sent to the server.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

export type OwnPhoto = { dataUrl: string; takenAt: string }

type OwnPhotos = {
  photos: Record<string, OwnPhoto>
  save: (id: string, dataUrl: string) => Promise<void>
  remove: (id: string) => Promise<void>
  clearAll: () => Promise<void>
}

const DB = 'keepsake'
const STORE = 'own-photos'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(STORE, mode).objectStore(STORE))
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

const Ctx = createContext<OwnPhotos | null>(null)

export function OwnPhotosProvider({ children }: { children: ReactNode }) {
  const [photos, setPhotos] = useState<Record<string, OwnPhoto>>({})

  useEffect(() => {
    Promise.all([run('readonly', (s) => s.getAllKeys()), run('readonly', (s) => s.getAll())])
      .then(([keys, values]) => setPhotos(Object.fromEntries(keys.map((k, i) => [String(k), values[i] as OwnPhoto]))))
      .catch(() => undefined)                         // private browsing without IndexedDB: no own photos
  }, [])

  const save = useCallback(async (id: string, dataUrl: string) => {
    const photo = { dataUrl, takenAt: new Date().toISOString() }
    await run('readwrite', (s) => s.put(photo, id))
    setPhotos((cur) => ({ ...cur, [id]: photo }))
  }, [])

  const remove = useCallback(async (id: string) => {
    await run('readwrite', (s) => s.delete(id))
    setPhotos((cur) => {
      const next = { ...cur }
      delete next[id]
      return next
    })
  }, [])

  const clearAll = useCallback(async () => {
    await run('readwrite', (s) => s.clear())
    setPhotos({})
  }, [])

  return <Ctx.Provider value={{ photos, save, remove, clearAll }}>{children}</Ctx.Provider>
}

export function useOwnPhotos(): OwnPhotos {
  const v = useContext(Ctx)
  if (!v) throw new Error('useOwnPhotos must be inside OwnPhotosProvider')
  return v
}
