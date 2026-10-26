import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import { FavoritesProvider } from './favorites'
import { OwnPhotosProvider } from './ownPhotos'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <FavoritesProvider>
        <OwnPhotosProvider>
          <App />
        </OwnPhotosProvider>
      </FavoritesProvider>
    </BrowserRouter>
  </StrictMode>,
)
