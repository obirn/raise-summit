import { Anchor, RotateCcw } from 'lucide-react'
import type { ReactNode } from 'react'
import type { SandboxState } from '../types'

type AppFrameProps = {
  children: ReactNode
  onConfigA: () => void
  onConfigB: () => void
  state: SandboxState
  title: string
  variant: 'desktop' | 'web'
}

export function AppFrame({
  children,
  onConfigA,
  onConfigB,
  state,
  title,
  variant,
}: AppFrameProps) {
  const isDesktop = variant === 'desktop'

  return (
    <div className="min-h-screen bg-slate-100 pb-48 text-slate-950 md:pb-28">
      <header className="sticky top-0 z-30 border-b border-slate-300 bg-white/95 shadow-sm backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isDesktop ? 'Docklock TMS Desktop' : 'Docklock Customs Web'}
            </p>
            <h1 className="text-2xl font-black text-slate-950">{title}</h1>
          </div>
          <div className="grid gap-2 font-mono text-xs sm:grid-cols-3">
            <div className="rounded border border-slate-300 bg-slate-50 px-3 py-2">
              TMS: <strong>{state.tms_status}</strong>
            </div>
            <div className="rounded border border-slate-300 bg-slate-50 px-3 py-2">
              ICS2: <strong>{state.customs_status}</strong>
            </div>
            <div className="rounded border border-slate-300 bg-slate-50 px-3 py-2">
              Invoice: <strong>{state.terminal_invoice_paid ? 'PAID' : 'OPEN'}</strong>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>

      <footer className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-700 bg-slate-950 text-white shadow-2xl">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2 font-mono text-xs">
            <span className="rounded border border-slate-700 px-2 py-1">
              Carrier: {state.carrier_status}
            </span>
            <span className="rounded border border-slate-700 px-2 py-1">
              Customs: {state.customs_status}
            </span>
            <span className="rounded border border-slate-700 px-2 py-1">
              Release: {state.tms_status}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border border-red-300 bg-red-50 px-4 text-sm font-black text-red-900 hover:bg-red-100"
              onClick={onConfigA}
            >
              <RotateCcw aria-hidden="true" size={16} />
              [Set Config A]
            </button>
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border border-emerald-300 bg-emerald-50 px-4 text-sm font-black text-emerald-900 hover:bg-emerald-100"
              onClick={onConfigB}
            >
              <Anchor aria-hidden="true" size={16} />
              [Set Config B]
            </button>
          </div>
        </div>
      </footer>
    </div>
  )
}
