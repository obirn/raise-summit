import { useCallback, useState } from 'react'
import {
  ensureTerminalChargesInitialized,
  nowStamp,
  saveTerminalCharges,
  type TerminalCharge,
} from '../lib/terminalChargesStorage'

/**
 * Normalize a gate reference for tolerant matching: drop everything but letters
 * and digits, uppercase. So "DET-4471-B", "det 4471 b" and a voice-mangled
 * "DET447.1B" all match the same charge (real gate references arrive over the
 * phone via ASR, which drops dashes / adds dots).
 */
function normalizeRef(reference: string): string {
  return reference.toUpperCase().replace(/[^A-Z0-9]/g, '')
}

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
      const key = normalizeRef(reference)
      return charges.find((c) => normalizeRef(c.reference) === key)
    },
    [charges],
  )

  const payCharge = useCallback(
    (reference: string) => {
      const key = normalizeRef(reference)
      persist(
        charges.map((c) =>
          normalizeRef(c.reference) === key ? { ...c, paid: true, paidAt: nowStamp() } : c,
        ),
      )
    },
    [charges, persist],
  )

  return { charges, findByReference, payCharge }
}
