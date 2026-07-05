import { useState } from 'react'
import { AlertTriangle, CheckCircle2, CreditCard, Lock, Search } from 'lucide-react'
import { useTerminalCharges } from '../hooks/useTerminalCharges'

// Terminal gate portal. A detention charge exists in localStorage but is only
// REVEALED when the exact reference is looked up (invariant 6). "Pay & release"
// flips it paid. Stable data-field hooks make Computer Use's read deterministic.
export function TerminalPortal() {
  const { findByReference, payCharge } = useTerminalCharges()
  const [input, setInput] = useState('')
  const [queried, setQueried] = useState<string | null>(null)

  const charge = queried ? findByReference(queried) : undefined
  const notFound = queried !== null && queried.trim() !== '' && !charge

  return (
    <div className="min-h-screen bg-terminal-slate px-6 py-8 font-mono text-slate-200">
      <div className="mx-auto max-w-3xl">
        <header className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-sm bg-terminal-panel text-terminal-green">
            <Lock aria-hidden="true" size={24} />
          </div>
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">
              Valencia Terminal · Gate Operations
            </p>
            <h1 className="text-2xl font-black text-white">Detention & Charge Lookup</h1>
          </div>
        </header>

        <section className="rounded-md border border-slate-700 bg-terminal-panel p-5">
          <label className="mb-2 block text-xs uppercase tracking-widest text-slate-500">
            Enter gate reference to release container
          </label>
          <div className="flex gap-2">
            <input
              data-field="reference_input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && setQueried(input)}
              placeholder="e.g. DET-0000-A"
              className="flex-1 rounded border border-slate-600 bg-terminal-slate px-3 py-2 uppercase text-white placeholder:text-slate-600 focus:border-terminal-green focus:outline-none"
            />
            <button
              data-field="lookup_button"
              onClick={() => setQueried(input)}
              className="inline-flex items-center gap-2 rounded bg-terminal-green px-4 py-2 font-black text-terminal-slate hover:brightness-110"
            >
              <Search aria-hidden="true" size={16} /> Look up
            </button>
          </div>

          {/* nothing shown until a valid reference is looked up (invariant 6) */}
          {queried === null && (
            <p data-field="empty_state" className="mt-4 text-sm text-slate-500">
              No charge displayed. Enter the gate reference from the driver's ticket.
            </p>
          )}

          {notFound && (
            <p data-field="not_found" className="mt-4 flex items-center gap-2 text-sm text-slate-400">
              <AlertTriangle aria-hidden="true" size={16} /> No charge on file for “{queried}”.
            </p>
          )}

          {charge && (
            <div
              data-field="charge_panel"
              data-detention-unpaid={String(!charge.paid)}
              data-amount-usd={String(charge.amount)}
              data-paid={String(charge.paid)}
              data-reference={charge.reference}
              className="mt-5 rounded border border-slate-700 bg-terminal-slate p-4"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-widest text-slate-500">
                    {charge.type} · {charge.containerId}
                  </p>
                  <p className="text-lg font-black text-white">
                    Reference <span className="text-terminal-green">{charge.reference}</span>
                  </p>
                </div>
                <div className="text-right">
                  <p data-field="amount_usd" className="text-3xl font-black text-white">
                    ${charge.amount}
                  </p>
                  <p className="text-xs uppercase tracking-widest text-slate-500">{charge.currency}</p>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-slate-700 pt-4">
                {charge.paid ? (
                  <span
                    data-field="status"
                    className="inline-flex items-center gap-2 rounded bg-terminal-green/15 px-3 py-1 font-black text-terminal-green"
                  >
                    <CheckCircle2 aria-hidden="true" size={16} /> PAID — GATE OPEN
                  </span>
                ) : (
                  <>
                    <span
                      data-field="status"
                      className="inline-flex items-center gap-2 rounded bg-red-500/15 px-3 py-1 font-black text-red-400"
                    >
                      <AlertTriangle aria-hidden="true" size={16} /> UNPAID — GATE HELD
                    </span>
                    <button
                      data-field="pay_button"
                      onClick={() => payCharge(charge.reference)}
                      className="inline-flex items-center gap-2 rounded bg-terminal-green px-5 py-2.5 font-black text-terminal-slate hover:brightness-110"
                    >
                      <CreditCard aria-hidden="true" size={16} /> Pay & release
                    </button>
                  </>
                )}
              </div>
              {charge.paid && charge.paidAt && (
                <p data-field="paid_at" className="mt-2 text-xs text-slate-500">
                  Settled {charge.paidAt}
                </p>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
