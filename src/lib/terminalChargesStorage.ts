// Terminal gate charges — persisted in browser localStorage (the portal's own
// state). The detention charge always EXISTS here; the terminal UI only reveals
// it when the operator/agent enters the exact reference (invariant 6). Computer
// Use reaches this only through the rendered page — never a backend.

export const TERMINAL_CHARGES_STORAGE_KEY = 'docklock_terminal_charges_v1'

export const TERMINAL_REFERENCE = 'DET-4471-B'
export const TERMINAL_DETENTION_USD = 340

export type TerminalCharge = {
  reference: string // 'DET-4471-B'
  containerId: string // 'MSKU4471'
  type: string // 'Detention'
  amount: number // 340
  currency: string // 'USD'
  paid: boolean // the mutable flag CU flips via "Pay & release"
  paidAt?: string
}

/** Seed written when localStorage is empty or reset. */
export const DEFAULT_TERMINAL_CHARGES: TerminalCharge[] = [
  {
    reference: TERMINAL_REFERENCE,
    containerId: 'MSKU4471',
    type: 'Detention',
    amount: TERMINAL_DETENTION_USD,
    currency: 'USD',
    paid: false,
  },
]

/** Timestamp for the paid marker: YYYY-MM-DD HH:MM:SS. */
export function nowStamp(date = new Date()): string {
  const pad = (v: number) => String(v).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function isTerminalCharge(value: unknown): value is TerminalCharge {
  if (!value || typeof value !== 'object') return false
  const c = value as TerminalCharge
  return (
    typeof c.reference === 'string' &&
    typeof c.containerId === 'string' &&
    typeof c.amount === 'number' &&
    typeof c.paid === 'boolean'
  )
}

function hydrate(charges: TerminalCharge[]): TerminalCharge[] {
  const byRef = new Map(DEFAULT_TERMINAL_CHARGES.map((c) => [c.reference, c]))
  charges.forEach((c) => byRef.set(c.reference, { ...byRef.get(c.reference), ...c }))
  return Array.from(byRef.values())
}

export function loadTerminalCharges(): TerminalCharge[] {
  try {
    const raw = localStorage.getItem(TERMINAL_CHARGES_STORAGE_KEY)
    if (!raw) return [...DEFAULT_TERMINAL_CHARGES]
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed) || !parsed.every(isTerminalCharge)) {
      return [...DEFAULT_TERMINAL_CHARGES]
    }
    return hydrate(parsed)
  } catch {
    return [...DEFAULT_TERMINAL_CHARGES]
  }
}

export function saveTerminalCharges(charges: TerminalCharge[]): void {
  localStorage.setItem(TERMINAL_CHARGES_STORAGE_KEY, JSON.stringify(charges))
}

export function ensureTerminalChargesInitialized(): TerminalCharge[] {
  const charges = loadTerminalCharges()
  saveTerminalCharges(charges)
  return charges
}
