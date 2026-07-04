import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { CarrierWebApp } from './apps/CarrierWebApp'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CarrierWebApp />
  </StrictMode>,
)
