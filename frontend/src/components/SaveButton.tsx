import { useFavorites } from '../favorites'

export default function SaveButton({ id, big = false }: { id: string; big?: boolean }) {
  const { isSaved, toggle } = useFavorites()
  const saved = isSaved(id)
  return (
    <button
      type="button"
      className={`save-btn ${saved ? 'saved' : ''} ${big ? 'big' : ''}`}
      aria-pressed={saved}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        toggle(id)
      }}
      title={saved ? 'Remove from my book' : 'Save to my book'}
    >
      <span aria-hidden>{saved ? '♥' : '♡'}</span>
      {big ? (saved ? ' Saved to my book' : ' Save to my book') : <span className="sr-only">{saved ? 'Saved' : 'Save'}</span>}
    </button>
  )
}
