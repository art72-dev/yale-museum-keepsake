// Carries a scan the scanner couldn't match (its photo and what the label said) to the "Add it yourself"
// form. Kept in memory only: a reload starts the form empty.
import type { PhotoReading } from './api'

type HandOff = { photo: string | null; reading: PhotoReading | null }

let pending: HandOff | null = null

export function handOff(photo: string | null, reading: PhotoReading | null) {
  pending = { photo, reading }
}

export function readHandOff(): HandOff | null {
  return pending
}
