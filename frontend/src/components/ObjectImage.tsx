import { useState } from 'react'
import { imageUrl } from '../api'
import { useOwnPhotos } from '../ownPhotos'

type Props = {
  id: string
  title: string
  usable: boolean
  rights: string
  size?: 'thumb' | 'large'
  alt?: string
  museumUrl?: string
}

// Only images whose rights allow reuse are shown (the backend refuses the rest too). For the others,
// the visitor's own photo is shown if they added one; otherwise a placeholder with a link.
export default function ObjectImage({ id, title, usable, rights, size = 'thumb', alt, museumUrl }: Props) {
  const [failed, setFailed] = useState(false)
  const { photos } = useOwnPhotos()
  const mine = !usable ? photos[id] : undefined
  if (usable && !failed) {
    return (
      <img className={`obj-img obj-img-${size}`} src={imageUrl(id, size)} alt={alt || title}
           loading="lazy" onError={() => setFailed(true)} />
    )
  }
  if (mine) {
    return (
      <div className="own-photo">
        <img className={`obj-img obj-img-${size}`} src={mine.dataUrl} alt={`Your photo of ${title}`} />
        <span className="own-badge">Your photo</span>
      </div>
    )
  }
  return (
    <div className={`obj-img obj-img-${size} img-placeholder`} role="img" aria-label={`No image: ${title}`}>
      <span className="ph-mark">◇</span>
      <span className="ph-text">
        {failed ? 'Image unavailable right now' : rights === 'No image' ? 'No photograph yet' : 'Image not shown'}
      </span>
      {!failed && rights !== 'No image' && <span className="ph-why">Rights: {rights}</span>}
      {museumUrl && !failed && (
        <a className="ph-link" href={museumUrl} target="_blank" rel="noreferrer">See it on the museum's site</a>
      )}
    </div>
  )
}
