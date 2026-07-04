import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { TmsDesktopApp } from './apps/TmsDesktopApp'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TmsDesktopApp />
  </StrictMode>,
)
