import { useState } from 'react'
import type { SandboxState } from '../types'

export const VALID_HS_CODE = '950300'

export const configA: SandboxState = {
  tms_status: 'DOCUMENTS HOLD',
  carrier_status: 'NO HOLD',
  customs_status: 'REJECTED',
  customs_hs_code: '870899',
  terminal_invoice_paid: false,
}

export const configB: SandboxState = {
  tms_status: 'PENDING RELEASE',
  carrier_status: 'NO HOLD',
  customs_status: 'PENDING',
  customs_hs_code: VALID_HS_CODE,
  terminal_invoice_paid: false,
}

export function deriveTmsStatus(next: SandboxState): SandboxState {
  if (next.customs_status === 'RELEASED' && next.terminal_invoice_paid) {
    return { ...next, tms_status: 'TRUE RELEASE' }
  }

  if (next.customs_status === 'REJECTED') {
    return { ...next, tms_status: 'DOCUMENTS HOLD' }
  }

  return { ...next, tms_status: 'PENDING RELEASE' }
}

export function useSandboxState() {
  const [sandbox, setSandbox] = useState<SandboxState>(configA)

  return {
    sandbox,
    setSandbox,
    setConfigA: () => setSandbox(configA),
    setConfigB: () => setSandbox(configB),
  }
}
