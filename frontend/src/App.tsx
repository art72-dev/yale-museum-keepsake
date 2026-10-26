import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { Dino } from './components/Art'
import { useFavorites } from './favorites'
import Browse from './pages/Browse'
import Home from './pages/Home'
import MyBook from './pages/MyBook'
import ObjectPage from './pages/ObjectPage'
import PrintBook from './pages/PrintBook'
import Scan from './pages/Scan'

export default function App() {
  const { ids } = useFavorites()
  return (
    <>
      <div className="bg-blobs no-print" aria-hidden><span /><span /><span /></div>
      <header className="nav no-print">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden><i /><i /><i /></span> Yale Museum <em>Keepsake</em>
        </Link>
        <nav>
          <NavLink to="/scan" className="scan-link">Scan</NavLink>
          <NavLink to="/" end>Museums</NavLink>
          <NavLink to="/museum/all">Search</NavLink>
          <NavLink to="/book" className="book-link">
            My book <span className="badge">{ids.length}</span>
          </NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/museum/:slug" element={<Browse />} />
          <Route path="/object/:id" element={<ObjectPage />} />
          <Route path="/scan" element={<Scan />} />
          <Route path="/book" element={<MyBook />} />
          <Route path="/book/print" element={<PrintBook />} />
          <Route path="*" element={
            <div className="not-found">
              <Dino />
              <div><h1>This gallery is closed.</h1><p className="lede">Even our dinosaur couldn't find that page.</p>
                <Link className="btn btn-pink" to="/">Back to the museums</Link></div>
            </div>} />
        </Routes>
      </main>
      <footer className="foot no-print">
        Collection data and images: Yale University museums and libraries, via{' '}
        <a href="https://lux.collections.yale.edu" target="_blank" rel="noreferrer">LUX</a>. Images shown only when
        public domain or CC0, or for Library objects made before 1900, under{' '}
        <a href="https://guides.library.yale.edu/openaccess" target="_blank" rel="noreferrer">Yale's Open Access policy</a>.
      </footer>
    </>
  )
}
