import { useRef, useState } from 'react'
import { useOwnPhotos } from '../ownPhotos'
import { toJpeg } from '../photo'

/** For a work whose museum image can't be printed: add, replace or remove the visitor's own photo.
 *  `offer` is a photo already in hand (e.g. the one just scanned), offered with one tap. */
export default function OwnPhotoControls({ id, rights, offer }: { id: string; rights: string; offer?: string | null }) {
  const { photos, save, remove } = useOwnPhotos()
  const [error, setError] = useState('')
  const camera = useRef<HTMLInputElement>(null)
  const library = useRef<HTMLInputElement>(null)
  const mine = photos[id]

  const pick = async (file: File | undefined) => {
    if (!file) return
    setError('')
    try {
      await save(id, await toJpeg(file))
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    } finally {
      if (camera.current) camera.current.value = ''
      if (library.current) library.current.value = ''
    }
  }

  return (
    <div className="own-photo-box">
      {mine ? (
        <p>
          <b>Your photo</b> is on this page of your book. The museum's own image isn't cleared for reuse ({rights}).
          It stays in this browser only.
        </p>
      ) : (
        <p>
          <b>The museum's image can't be printed</b> ({rights}). Use your own photo of the work instead. It stays in
          this browser only.
        </p>
      )}
      <div className="own-photo-actions">
        {!mine && offer && (
          <button className="btn btn-pink" onClick={() => save(id, offer).catch((e) => setError(String(e)))}>
            Use the photo I just took
          </button>
        )}
        <button className={`btn ${!mine && !offer ? 'btn-pink' : ''}`} onClick={() => camera.current?.click()}>
          📷 {mine ? 'Retake' : 'Take a photo'}
        </button>
        <button className="btn" onClick={() => library.current?.click()}>{mine ? 'Choose another' : 'Choose a photo'}</button>
        {mine && <button className="btn" onClick={() => remove(id)}>Remove my photo</button>}
      </div>
      <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => pick(e.target.files?.[0])} />
      <input ref={library} type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files?.[0])} />
      {error && <p className="error">{error}</p>}
    </div>
  )
}
