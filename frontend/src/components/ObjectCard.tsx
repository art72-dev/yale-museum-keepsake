import { Link } from 'react-router-dom'
import { byline, type ObjectCard as Card } from '../api'
import ObjectImage from './ObjectImage'
import SaveButton from './SaveButton'

export default function ObjectCard({ o }: { o: Card }) {
  return (
    <article className="card">
      <Link to={`/object/${o.id}`} className="card-link">
        <ObjectImage id={o.id} title={o.title} usable={o.image_usable} rights={o.rights} />
        <div className="card-body">
          <h3>{o.title}</h3>
          <p className="byline">{byline(o)}</p>
          <p className="meta">
            {[...new Set([o.type, o.department].filter(Boolean))].join(' · ')}
          </p>
        </div>
      </Link>
      <SaveButton id={o.id} />
    </article>
  )
}
