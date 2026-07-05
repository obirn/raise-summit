import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { TerminalWebApp } from './apps/TerminalWebApp'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TerminalWebApp />
  </StrictMode>,
)
