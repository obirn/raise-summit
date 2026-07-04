import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { CoordinatorApp } from './apps/CoordinatorApp'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CoordinatorApp />
  </StrictMode>,
)
