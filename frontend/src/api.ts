// Types and calls for the FastAPI backend (backend/main.py).

export type MuseumInfo = {
  tagline: string
  blurb: string
  address: string
  admission: string
  status: string
  hours: { place: string; rows: { days: string; time: string }[] }[]   // from the museum's own website
  hours_summary: string
  hours_note: string
  hours_source: string
  hours_checked: string
  website: string
  sources: string[]
}

export type MuseumSummary = {
  info: MuseumInfo | null
  slug: string
  name: string
  objects: number
  printable_images: number
  on_view: number
  departments: string[]
  cover_id: string | null
}

export type ObjectCard = {
  id: string
  title: string
  maker: string
  collected_by: string
  date: string
  date_kind: string
  type: string
  museum: string
  museum_slug: string
  department: string
  accession_number: string
  on_view: boolean
  location: string
  image_usable: boolean
  rights: string
  added_by_visitor?: boolean      // the visitor typed this object in themselves (private to them)
}

export type ObjectDetail = ObjectCard & {
  creators_display: string
  collectors: string
  classification: string
  medium: string
  dimensions: string
  culture: string
  period: string
  description: string
  credit_line: string
  access_statement: string
  alt_text: string
  notes: Record<string, string[]>
  image_rights_statement: string
  image_flag_reason: string
  object_copyright: string
  image_count: number | string
  museum_page_url: string
  lux_url: string
  related: { id: string; title: string; maker: string; date: string; why: string }[]
  label_text?: string               // added objects only: the label text the visitor copied
  visitor_note?: string             // added objects only: their own note, printed but never sent to the AI
}

/** What a visitor types to add an object of their own. */
export type AddedForm = {
  museum: string
  title: string
  maker: string
  date: string
  type: string
  medium: string
  dimensions: string
  department: string
  object_number: string
  label_text: string
  note: string
}

export type AddResponse =
  | { status: 'possible_duplicates'; candidates: (ObjectCard & { match: string })[] }
  | { status: 'created'; object: ObjectCard; book: string[]; note: string }

/** The `rights` value of an object the visitor added (it has no museum image). */
export const ADDED = 'Added by you'

export type SearchPage = {
  total: number
  page: number
  page_size: number
  items: ObjectCard[]
  hidden: { department: string; kind: string; count: number }[]   // look-alikes left out of plain browsing
}

export type Blurb = {
  object_id: string
  headline: string
  blurb: string
  look_closer: string | null
  source: 'ai' | 'cache' | 'fallback'
  model: string | null
  note: string | null
}

export type PhotoReading = {
  kind: 'label' | 'artwork' | 'label and artwork' | 'unclear'
  title: string
  maker: string
  date: string
  object_number: string
  museum: string
  keywords: string
  description: string
}

export type ScanResponse = {
  status: 'added' | 'choose' | 'not_found' | 'error'
  message: string
  reading: PhotoReading | null
  object: ObjectCard | null
  blurb: Blurb | null
  candidates: ObjectCard[]
  book: string[]
  steps: { tool: string; summary: string }[]
}

function visitorId(): string {
  let id = localStorage.getItem('keepsake.visitor')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('keepsake.visitor', id)
  }
  return id
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { 'x-visitor-id': visitorId() } })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  museums: () => get<MuseumSummary[]>('/api/museums'),
  search: (p: { museum?: string; q?: string; printable?: boolean; department?: string; page?: number }) => {
    const qs = new URLSearchParams()
    if (p.museum && p.museum !== 'all') qs.set('museum', p.museum)
    if (p.q) qs.set('q', p.q)
    if (p.printable) qs.set('printable', 'true')
    if (p.department) qs.set('department', p.department)
    qs.set('page', String(p.page ?? 1))
    return get<SearchPage>(`/api/objects?${qs}`)
  },
  object: (id: string) => get<ObjectDetail>(`/api/objects/${id}`),
  blurb: (id: string) => get<Blurb>(`/api/objects/${id}/blurb`),
  getBook: () => get<{ ids: string[] }>('/api/book').then((r) => r.ids),
  putBook: (ids: string[]) => send<{ ids: string[] }>('PUT', '/api/book', { ids }),
  scan: (image: string) => send<ScanResponse>('POST', '/api/scan', { image }),
  addedList: () => get<ObjectCard[]>('/api/added'),
  addObject: (form: AddedForm, confirmNew: boolean) =>
    send<AddResponse>('POST', '/api/added', { ...form, confirm_new: confirmNew }),
  updateAdded: (id: string, form: AddedForm) => send<{ object: ObjectCard }>('PUT', `/api/added/${id}`, form),
  deleteAdded: (id: string) => send<{ book: string[] }>('DELETE', `/api/added/${id}`),
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { 'x-visitor-id': visitorId(), 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await errorText(res))
  return res.json() as Promise<T>
}

/** FastAPI's error as one readable line ("title: String should have at least 1 character"). */
async function errorText(res: Response): Promise<string> {
  const text = await res.text()
  try {
    const d = JSON.parse(text).detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) return d.map((e) => `${e.loc?.slice(-1)[0] ?? ''}: ${e.msg}`).join('; ')
  } catch {
    /* not JSON */
  }
  return `${res.status} ${text}`
}

/** Library images used under Yale's Open Access policy because the work was made before 1900. */
export const OPEN_ACCESS = 'Public domain by date (Yale Open Access policy)'
export const OPEN_ACCESS_URL = 'https://guides.library.yale.edu/openaccess'

export const imageUrl = (id: string, size: 'thumb' | 'large' = 'thumb') => `/api/objects/${id}/image?size=${size}`

/** "Artist: Vincent van Gogh (Dutch, 1853–1890)" -> "Vincent van Gogh (Dutch, 1853–1890)" */
export function cleanMaker(maker: string): string {
  return maker
    .split(' | ')
    .map((m) => m.replace(/^(Artist|Maker|Manufacturer|Primary Artist|Printmaker|Publisher):\s*(\(Made by\)\s*)?/i, '').trim())
    .filter((m) => m && !/^unknown$/i.test(m))
    .join(', ')
}

/** The full maker line for an object page: each person with roles and dates, one after another. */
export function makerDetail(display: string): string {
  return display
    .split(' | ')
    .map((m) => m.replace(/^(Artist|Maker|Manufacturer|Primary Artist|Printmaker|Publisher):\s*(\(Made by\)\s*)?/i, '').trim())
    .filter((m) => m && !/^unknown$/i.test(m))
    .join(' · ')
}

export function byline(o: Pick<ObjectCard, 'maker' | 'collected_by' | 'date' | 'date_kind'>): string {
  const date = /^(n\.d\.?|undated|no date)$/i.test(o.date.trim()) ? '' : o.date
  const maker = cleanMaker(o.maker)
  if (maker) return [maker, date].filter(Boolean).join(', ')
  if (o.collected_by) return `Collected by ${cleanMaker(o.collected_by)}${date ? `, ${date}` : ''}`
  return date
}
