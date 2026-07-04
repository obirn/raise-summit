import { useCallback, useState } from 'react'
import {
  ensureTerminalChargesInitialized,
  nowStamp,
  saveTerminalCharges,
  type TerminalCharge,
} from '../lib/terminalChargesStorage'

/**
 * Terminal gate charges with immediate localStorage persistence. A "Pay &
 * release" click flips `paid` so any subsequent read (re-mount, another tab,
 * or Computer Use re-reading the page) sees the change.
 */
export function useTerminalCharges() {
  const [charges, setCharges] = useState<TerminalCharge[]>(ensureTerminalChargesInitialized)

  const persist = useCallback((next: TerminalCharge[]) => {
    setCharges(next)
    saveTerminalCharges(next)
  }, [])

  const findByReference = useCallback(
    (reference: string): TerminalCharge | undefined => {
      const key = reference.trim().toUpperCase()
      return charges.find((c) => c.reference.toUpperCase() === key)
    },
    [charges],
  )

  const payCharge = useCallback(
    (reference: string) => {
      const key = reference.trim().toUpperCase()
      persist(
        charges.map((c) =>
          c.reference.toUpperCase() === key ? { ...c, paid: true, paidAt: nowStamp() } : c,
        ),
      )
    },
    [charges, persist],
  )

  return { charges, findByReference, payCharge }
}
