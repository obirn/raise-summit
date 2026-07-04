import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { CustomsWebApp } from './apps/CustomsWebApp'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CustomsWebApp />
  </StrictMode>,
)
