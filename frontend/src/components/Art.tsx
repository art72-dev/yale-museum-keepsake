// Animated art pieces, drawn in SVG (no image files): a Calder-style mobile, a marble bust in a beret,
// a Peabody dinosaur skeleton, a violin that plays itself, two paintings and a library book.
// Motion lives in art.css and stops for visitors who ask for reduced motion.
import { useId } from 'react'
import './art.css'

type P = { className?: string }

export function Mobile({ className = '' }: P) {
  return (
    <svg className={`art art-mobile ${className}`} viewBox="0 0 330 200" role="img" aria-label="A hanging mobile, gently turning">
      <line className="wire" x1="150" y1="0" x2="150" y2="28" />
      <g className="m-arm1">
        <path className="wire" d="M40 36 Q150 18 250 34" />
        <g className="m-hang m-h1">
          <line className="wire" x1="40" y1="36" x2="40" y2="92" />
          <circle cx="40" cy="112" r="20" fill="var(--rose)" />
        </g>
        <g className="m-hang m-h2">
          <line className="wire" x1="100" y1="27" x2="100" y2="66" />
          <path d="M100 66 C122 74 124 102 100 116 C78 102 80 74 100 66Z" fill="var(--plum)" />
        </g>
        <g className="m-arm2">
          <line className="wire" x1="250" y1="34" x2="250" y2="64" />
          <path className="wire" d="M196 70 Q250 58 302 66" />
          <g className="m-hang m-h3">
            <line className="wire" x1="196" y1="70" x2="196" y2="118" />
            <path d="M196 118 L219 158 L173 158 Z" fill="var(--ochre)" />
          </g>
          <g className="m-hang m-h4">
            <line className="wire" x1="302" y1="66" x2="302" y2="104" />
            <path d="M302 104 A24 24 0 0 0 302 152 A30 30 0 0 1 302 104 Z" fill="var(--teal)" />
          </g>
        </g>
      </g>
    </svg>
  )
}

export function Bust({ className = '' }: P) {
  return (
    <svg className={`art art-bust ${className}`} viewBox="0 0 160 232" role="img" aria-label="A marble bust in a pink beret, blinking">
      <rect x="34" y="220" width="92" height="10" rx="2" fill="#d6cbbc" />
      <rect x="44" y="176" width="72" height="46" fill="#e6ddd1" />
      <rect x="26" y="166" width="108" height="12" rx="3" fill="#d9cfc1" />
      <path d="M30 168 Q34 126 80 118 Q126 126 130 168 Z" fill="var(--marble)" />
      <path d="M48 160 Q60 140 80 138 M112 160 Q100 140 80 138 M64 166 Q72 150 80 148" stroke="#d8cdbd" strokeWidth="2" fill="none" />
      <path d="M68 98 L67 122 L93 122 L92 98 Z" fill="var(--marble)" />
      <g className="b-head">
        <ellipse cx="80" cy="64" rx="34" ry="36" fill="#e2d8ca" />
        <ellipse cx="80" cy="70" rx="29" ry="35" fill="var(--marble)" />
        {[[56, 46, 9], [67, 38, 9], [79, 35, 9], [91, 37, 9], [102, 44, 9], [51, 58, 7], [109, 57, 7]].map(([x, y, r]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill="#e8dfd2" stroke="#d6cab9" strokeWidth="1.2" />
        ))}
        <g className="b-beret">
          <ellipse cx="74" cy="33" rx="31" ry="11" fill="var(--rose)" transform="rotate(-12 74 33)" />
          <circle cx="72" cy="21" r="3.2" fill="var(--rose-deep)" />
        </g>
        <path d="M63 64 Q69 61 75 64 M85 64 Q91 61 97 64" stroke="#bfb1a0" strokeWidth="1.6" fill="none" strokeLinecap="round" />
        <g className="b-eyes">
          <ellipse cx="69" cy="71" rx="3" ry="2.3" fill="#8e8277" />
          <ellipse cx="91" cy="71" rx="3" ry="2.3" fill="#8e8277" />
        </g>
        <path d="M80 72 L76 87 Q80 90 84 87" fill="none" stroke="#cbbdac" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="64" cy="84" r="5" fill="var(--rose)" opacity=".22" />
        <circle cx="96" cy="84" r="5" fill="var(--rose)" opacity=".22" />
        <path d="M72 95 Q80 101 88 95" fill="none" stroke="#c3a39b" strokeWidth="1.8" strokeLinecap="round" />
      </g>
    </svg>
  )
}

export function Dino({ className = '' }: P) {
  const ribs = [[114, 80], [126, 74], [138, 71], [150, 70], [162, 71], [174, 75]]
  return (
    <svg className={`art art-dino ${className}`} viewBox="0 0 300 170" role="img" aria-label="A dinosaur skeleton swishing its tail">
      <line x1="10" y1="156" x2="290" y2="156" stroke="var(--line-strong)" strokeWidth="2" strokeDasharray="2 7" strokeLinecap="round" />
      <g className="bone">
        <path d="M100 90 L95 122 L101 152 M92 154 L110 154" />
        <path d="M182 82 L185 120 L178 152 M170 154 L188 154" />
        {ribs.map(([x, y]) => <path key={x} d={`M${x} ${y} q-9 18 -3 34`} />)}
        <ellipse cx="101" cy="88" rx="13" ry="8" />
        <ellipse cx="183" cy="80" rx="11" ry="7" />
      </g>
      <path className="spine" d="M100 88 Q142 58 185 78" />
      <g className="d-tail">
        <path className="spine" d="M100 88 Q60 96 34 118 Q18 130 6 127" />
      </g>
      <g className="d-neck">
        <path className="spine" d="M185 78 Q216 60 228 32" />
        <path className="bone skull" d="M224 31 q8 -13 27 -7 q7 4 -1 11 q-13 5 -26 -4 Z" />
        <circle cx="240" cy="27" r="2.6" fill="var(--sepia)" />
      </g>
    </svg>
  )
}

export function Violin({ className = '' }: P) {
  return (
    <svg className={`art art-violin ${className}`} viewBox="0 0 130 250" role="img" aria-label="A violin playing itself">
      <g className="v-body">
        <circle cx="62" cy="15" r="7" fill="#8a5a36" />
        <rect x="58" y="19" width="8" height="58" rx="2" fill="#8a5a36" />
        <path d="M62 72 C37 72 30 90 36 106 C40 116 40 122 36 132 C28 152 32 186 62 188 C92 186 96 152 88 132 C84 122 84 116 88 106 C94 90 87 72 62 72 Z"
              fill="var(--terracotta)" stroke="#9b5e3d" strokeWidth="2" />
        <path d="M62 80 C44 80 40 94 44 106 M62 80 C80 80 84 94 80 106" stroke="#e3a37f" strokeWidth="2" fill="none" opacity=".7" />
        <rect x="58.5" y="27" width="7" height="112" rx="2" fill="#3e2c22" />
        <path d="M46 136 q-5 10 0 20 M78 136 q5 10 0 20" stroke="#5b3a26" strokeWidth="2.4" fill="none" strokeLinecap="round" />
        <rect x="50" y="154" width="24" height="4" rx="1" fill="#f0dcb4" />
        <path d="M56 170 L68 170 L66 186 L58 186 Z" fill="#3e2c22" />
        <g className="v-strings">
          {[59.8, 61.3, 62.7, 64.2].map((x) => <line key={x} x1={x} y1="20" x2={x} y2="170" stroke="#f7ecd5" strokeWidth=".7" />)}
        </g>
      </g>
      <text className="v-note v-n1" x="98" y="70">♪</text>
      <text className="v-note v-n2" x="14" y="96">♫</text>
      <text className="v-note v-n3" x="104" y="122">♪</text>
    </svg>
  )
}

export function Painting({ kind = 'abstract', className = '' }: P & { kind?: 'abstract' | 'landscape' }) {
  const clip = `clip-${useId().replace(/:/g, '')}`
  const sky = `sky-${useId().replace(/:/g, '')}`
  return (
    <svg className={`art art-painting ${className}`} viewBox="0 0 200 160" role="img"
         aria-label={kind === 'abstract' ? 'A framed painting of drifting paper cut-out shapes' : 'A framed landscape with drifting clouds'}>
      <defs>
        <clipPath id={clip}><rect x="14" y="14" width="172" height="132" /></clipPath>
        <linearGradient id={sky} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#a9bfdc" />
          <stop offset="1" stopColor="#f2d9c6" />
        </linearGradient>
      </defs>
      <rect x="14" y="14" width="172" height="132" fill={kind === 'abstract' ? '#f7f0e5' : `url(#${sky})`} />
      <g clipPath={`url(#${clip})`}>
        {kind === 'abstract' ? (
          <>
            <path className="p-drift1" d="M42 128 C30 104 52 94 46 72 C42 56 60 50 63 66 C65 82 54 94 64 110 C71 122 55 134 42 128Z" fill="var(--teal)" />
            <circle className="p-drift2" cx="122" cy="58" r="22" fill="var(--rose)" />
            <path className="p-spin" d="M150 96 l7 14 15 2 -11 10 3 15 -14 -7 -14 7 3 -15 -11 -10 15 -2Z" fill="var(--ochre)" />
            <path className="p-drift3" d="M84 40 A16 16 0 0 0 84 72 A20 20 0 0 1 84 40 Z" fill="var(--plum)" />
            <rect className="p-drift2" x="96" y="104" width="30" height="14" rx="7" fill="var(--sage)" />
          </>
        ) : (
          <>
            <circle className="p-sun" cx="148" cy="54" r="16" fill="#efc07a" />
            <g className="p-cloud">
              <ellipse cx="40" cy="40" rx="18" ry="8" fill="#fbf6ee" />
              <ellipse cx="54" cy="36" rx="14" ry="9" fill="#fbf6ee" />
            </g>
            <g className="p-cloud p-cloud2">
              <ellipse cx="110" cy="30" rx="16" ry="7" fill="#fbf6ee" opacity=".9" />
              <ellipse cx="122" cy="27" rx="11" ry="7" fill="#fbf6ee" opacity=".9" />
            </g>
            <path d="M14 112 Q60 86 104 106 T186 98 L186 146 L14 146Z" fill="var(--sage)" />
            <path d="M14 128 Q70 110 130 126 T186 120 L186 146 L14 146Z" fill="#6f9071" />
            <path d="M58 104 l0 -14" stroke="#5c4636" strokeWidth="2.2" />
            <circle className="p-tree" cx="58" cy="86" r="9" fill="#5f8063" />
          </>
        )}
      </g>
      <rect x="9" y="9" width="182" height="142" rx="3" fill="none" stroke="#c9a463" strokeWidth="10" />
      <rect x="4" y="4" width="192" height="152" rx="4" fill="none" stroke="#b08a4c" strokeWidth="1.5" />
    </svg>
  )
}

export function Book({ className = '' }: P) {
  const lines = (x0: number, x1: number) =>
    [44, 54, 64, 74, 84, 94, 104].map((y, i) => (
      <line key={y} x1={x0} y1={y} x2={i === 6 ? (x0 + x1) / 2 : x1} y2={y} stroke="#d7cbbd" strokeWidth="2.4" strokeLinecap="round" />
    ))
  return (
    <svg className={`art art-book ${className}`} viewBox="0 0 200 140" role="img" aria-label="An open book turning its pages">
      <path d="M100 124 Q58 114 14 124 L14 32 L100 38 L186 32 L186 124 Q142 114 100 124Z" fill="var(--plum)" />
      <path d="M100 32 Q60 22 20 30 L20 118 Q60 110 100 120 Z" fill="#fbf6ee" stroke="#d5c8b8" />
      <path d="M100 32 Q140 22 180 30 L180 118 Q140 110 100 120 Z" fill="#fbf6ee" stroke="#d5c8b8" />
      {lines(32, 88)}
      {lines(112, 168)}
      <g className="bk-flip">
        <path d="M100 32 Q140 22 180 30 L180 118 Q140 110 100 120 Z" fill="#f4ebdf" stroke="#d5c8b8" />
        {lines(112, 168)}
      </g>
      <path d="M150 28 L150 58 L156 52 L162 58 L162 26" fill="var(--rose)" />
    </svg>
  )
}

/** Each museum's emblem. */
export function MuseumEmblem({ slug, className = '' }: { slug: string; className?: string }) {
  switch (slug) {
    case 'yuag': return <Painting kind="abstract" className={className} />
    case 'ycba': return <Painting kind="landscape" className={className} />
    case 'peabody': return <Dino className={className} />
    case 'musical_instruments': return <Violin className={className} />
    case 'yale_library': return <Book className={className} />
    default: return <Bust className={className} />
  }
}

export const MUSEUM_ACCENT: Record<string, string> = {
  yuag: 'var(--teal)',
  ycba: 'var(--cornflower)',
  peabody: 'var(--sage)',
  musical_instruments: 'var(--ochre)',
  campus_art: 'var(--rose)',
  yale_library: 'var(--plum)',
}

/** The home page's little gallery: a mobile, a painting, a bust and a skeleton sharing a wall. */
export function GalleryScene() {
  return (
    <div className="gallery-scene" aria-hidden>
      <div className="gs-wall" />
      <Mobile className="gs-mobile" />
      <Painting kind="abstract" className="gs-painting" />
      <Painting kind="landscape" className="gs-painting2" />
      <Bust className="gs-bust" />
      <Dino className="gs-dino" />
      <div className="gs-floor" />
    </div>
  )
}
