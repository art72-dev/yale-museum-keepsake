import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api, type AddedForm, type MuseumSummary, type ObjectCard as Card } from '../api'
import { Painting } from '../components/Art'
import ObjectCard from '../components/ObjectCard'
import { useFavorites } from '../favorites'
import { readHandOff } from '../handoff'
import { useOwnPhotos } from '../ownPhotos'
import { toJpeg } from '../photo'

const EMPTY: AddedForm = {
  museum: '', title: '', maker: '', date: '', type: '', medium: '', dimensions: '', department: '',
  object_number: '', label_text: '', note: '',
}

const TYPES = ['Painting', 'Drawing', 'Print', 'Photograph', 'Sculpture', 'Ceramic', 'Furniture', 'Textile', 'Coin',
  'Jewelry', 'Musical instrument', 'Manuscript', 'Book', 'Map', 'Fossil', 'Mineral', 'Specimen', 'Clay tablet', 'Tool']

/** The museum a label names ("Yale Center for British Art" -> its slug), if any. */
function museumFromLabel(text: string, museums: MuseumSummary[]): string {
  const t = text.toLowerCase().trim()
  if (!t) return ''
  return museums.find((m) => t.includes(m.name.toLowerCase()) || m.name.toLowerCase().includes(t))?.slug ?? ''
}

// Add an object that isn't in the app (or edit one you added). It goes into this visitor's book only.
export default function AddObject() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const location = useLocation()
  const { add, remove } = useFavorites()
  const { save: savePhoto, remove: removePhoto } = useOwnPhotos()
  const [museums, setMuseums] = useState<MuseumSummary[]>([])
  const [form, setForm] = useState<AddedForm>(EMPTY)
  const [photo, setPhoto] = useState<string | null>(null)
  const [scanPhoto, setScanPhoto] = useState<string | null>(null)
  const [dupes, setDupes] = useState<Card[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const labelMuseum = useRef('')
  const camera = useRef<HTMLInputElement>(null)
  const library = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.museums().then(setMuseums).catch(() => setError("Couldn't load the list of museums."))
  }, [])

  // Start from the object being edited, or from a scan the scanner couldn't match.
  useEffect(() => {
    if (id) {
      api.object(id)
        .then((o) => setForm({
          museum: o.museum_slug, title: o.title, maker: o.maker, date: o.date, type: o.type, medium: o.medium,
          dimensions: o.dimensions, department: o.department, object_number: o.accession_number,
          label_text: o.label_text ?? '', note: o.visitor_note ?? '',
        }))
        .catch(() => setError("Couldn't load this object."))
      return
    }
    const h = (location.state as { fromScan?: boolean } | null)?.fromScan ? readHandOff() : null
    if (h?.reading) {
      const r = h.reading
      setForm((f) => ({ ...f, title: r.title, maker: r.maker, date: r.date, object_number: r.object_number }))
      labelMuseum.current = r.museum
    }
    if (h?.photo) setScanPhoto(h.photo)
  }, [id, location.state])

  useEffect(() => {
    const slug = museumFromLabel(labelMuseum.current, museums)
    if (slug) setForm((f) => (f.museum ? f : { ...f, museum: slug }))
  }, [museums])

  const field = (key: keyof AddedForm) => ({
    value: form[key],
    onChange: (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value })),
  })
  const departments = museums.find((m) => m.slug === form.museum)?.departments ?? []

  async function pick(file: File | undefined) {
    if (!file) return
    try {
      setPhoto(await toJpeg(file))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (camera.current) camera.current.value = ''
      if (library.current) library.current.value = ''
    }
  }

  async function submit(e?: FormEvent, confirmNew = false) {
    e?.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (id) {
        await api.updateAdded(id, form)
        navigate(`/object/${id}`)
        return
      }
      const r = await api.addObject(form, confirmNew)
      if (r.status === 'possible_duplicates') {
        setDupes(r.candidates)
        window.scrollTo(0, 0)
        return
      }
      if (photo) await savePhoto(r.object.id, photo)
      add(r.object.id)                                 // the server already put it in the book; mirror that here
      navigate(`/object/${r.object.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function deleteIt() {
    if (!id || !window.confirm('Delete this object and its page from your book?')) return
    try {
      await api.deleteAdded(id)
      await removePhoto(id).catch(() => undefined)
      remove(id)
      navigate('/book')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  if (dupes) {
    return (
      <div className="add-page">
        <p className="eyebrow">Add an object</p>
        <h1>Is it one of these?</h1>
        <p className="lede">
          These are already in Yale's collection. Tap ♡ to save the museum's own record instead: it comes with the
          museum's details and, where allowed, its picture.
        </p>
        <div className="grid">{dupes.map((c) => <ObjectCard key={c.id} o={c} />)}</div>
        <div className="scan-actions">
          <button className="btn btn-pink" disabled={busy} onClick={() => submit(undefined, true)}>
            {busy ? 'Adding…' : 'None of these: add mine'}
          </button>
          <button className="btn" onClick={() => setDupes(null)}>Back to the form</button>
        </div>
        {error && <p className="error">{error}</p>}
      </div>
    )
  }

  return (
    <div className="add-page">
      <div className="add-head">
        <div>
          <p className="eyebrow">{editing ? 'Edit your object' : 'Add an object'}</p>
          <h1>{editing ? 'Fix the details' : 'Not in the app? Add it yourself.'}</h1>
          <p className="lede">
            Fill in what the wall label says. It goes into your book only: nobody else sees it, and its page says
            the details came from you, not from the museum's record.
          </p>
        </div>
        <Painting kind="landscape" />
      </div>

      <form className="add-form" onSubmit={submit}>
        <label className="req">
          <span>Museum</span>
          <select required {...field('museum')}>
            <option value="">Choose…</option>
            {museums.map((m) => <option key={m.slug} value={m.slug}>{m.name}</option>)}
          </select>
        </label>
        <label className="req">
          <span>What is it?</span>
          <input required maxLength={60} list="add-types" placeholder="e.g. Painting, Violin, Fossil" {...field('type')} />
        </label>
        <label className="req wide">
          <span>Title</span>
          <input required maxLength={200} placeholder="As on the label" {...field('title')} />
        </label>
        <label className="req">
          <span>Artist or maker</span>
          <input required maxLength={150} placeholder='As on the label, or "Unknown"' {...field('maker')} />
        </label>
        <label className="req">
          <span>Date or year</span>
          <input required maxLength={60} placeholder="e.g. 1745, ca. 1780, 18th century" {...field('date')} />
        </label>
        <label>
          <span>Materials</span>
          <input maxLength={200} placeholder="e.g. Oil on canvas" {...field('medium')} />
        </label>
        <label>
          <span>Size</span>
          <input maxLength={120} placeholder="e.g. 61 × 50 cm" {...field('dimensions')} />
        </label>
        <label>
          <span>Department</span>
          <input maxLength={80} list="add-depts" placeholder="If you know it" {...field('department')} />
        </label>
        <label>
          <span>Object number</span>
          <input maxLength={40} placeholder="On the label, e.g. 1958.59" {...field('object_number')} />
        </label>
        <label className="wide">
          <span>Label text</span>
          <textarea maxLength={1500} rows={4} {...field('label_text')}
                    placeholder="Copy the wall label, if there is one. The description is written only from what you enter on this form." />
        </label>
        <label className="wide">
          <span>Your note</span>
          <textarea maxLength={500} rows={2} {...field('note')}
                    placeholder="Why you liked it, who you were with… Printed on your page as your note. It isn't sent to the AI." />
        </label>
        <datalist id="add-types">{TYPES.map((t) => <option key={t} value={t} />)}</datalist>
        <datalist id="add-depts">{departments.map((d) => <option key={d} value={d} />)}</datalist>

        {!editing && (
          <div className="add-photo wide">
            {photo ? <img src={photo} alt="Your photo" /> : <div className="img-placeholder"><span className="ph-mark">◇</span></div>}
            <div>
              <p><b>Your photo</b> (optional). It stays in this browser only and prints marked "Your photo".</p>
              <div className="own-photo-actions">
                {scanPhoto && photo !== scanPhoto && (
                  <button type="button" className="btn" onClick={() => setPhoto(scanPhoto)}>Use the photo I just scanned</button>
                )}
                <button type="button" className="btn" onClick={() => camera.current?.click()}>📷 Take a photo</button>
                <button type="button" className="btn" onClick={() => library.current?.click()}>Choose a photo</button>
                {photo && <button type="button" className="btn" onClick={() => setPhoto(null)}>Remove photo</button>}
              </div>
            </div>
            <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => pick(e.target.files?.[0])} />
            <input ref={library} type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files?.[0])} />
          </div>
        )}

        <div className="add-actions wide">
          <button className="btn btn-pink" type="submit" disabled={busy}>
            {busy ? 'Saving…' : editing ? 'Save changes' : 'Add to my book'}
          </button>
          <Link className="btn" to={id ? `/object/${id}` : '/book'}>Cancel</Link>
          {editing && <button type="button" className="btn btn-danger" onClick={deleteIt}>Delete this object</button>}
          <span className="muted"><span className="req-mark">*</span> required</span>
        </div>
        {error && <p className="error wide">{error}</p>}
      </form>
    </div>
  )
}
