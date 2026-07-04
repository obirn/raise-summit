import { Anchor, CheckCircle2, Ship } from 'lucide-react'

// Carrier / maritime portal — shows vessel availability and any carrier hold.
// For the golden path MSKU4471 reads AVAILABLE · NO HOLD (clean), so the agent
// rules the carrier out while diagnosing. data-field hooks make CU's read exact.

type CarrierRow = {
  containerId: string
  vessel: string
  voyage: string
  status: string
  hold: boolean
}

const ROWS: CarrierRow[] = [
  { containerId: 'MSKU4471', vessel: 'Maersk Line', voyage: '2603W', status: 'AVAILABLE', hold: false },
  { containerId: 'MSKU5501', vessel: 'Maersk Line', voyage: '2603W', status: 'AVAILABLE', hold: false },
  { containerId: 'TCLU3380', vessel: 'MSC', voyage: '1407E', status: 'AVAILABLE', hold: false },
]

export function CarrierPortal() {
  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8 text-slate-900">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-sm bg-carrier-navy text-white">
            <Ship aria-hidden="true" size={24} />
          </div>
          <div>
            <p className="font-mono text-xs font-black uppercase tracking-[0.16em] text-slate-500">
              MAEU · Carrier eCommerce Portal
            </p>
            <h1 className="text-2xl font-black">Container Availability & Holds</h1>
          </div>
        </header>

        <section className="overflow-hidden rounded-md border border-slate-300 bg-white shadow-dock">
          <table className="w-full text-left text-sm">
            <thead className="bg-ics2-shell font-mono text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">Container</th>
                <th className="px-4 py-3">Vessel / Voyage</th>
                <th className="px-4 py-3">Carrier Status</th>
                <th className="px-4 py-3">Hold</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr
                  key={r.containerId}
                  data-field="carrier_row"
                  data-container={r.containerId}
                  data-status={r.status}
                  data-hold={String(r.hold)}
                  className="border-t border-slate-200"
                >
                  <td className="px-4 py-3 font-mono font-bold">{r.containerId}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {r.vessel} <span className="text-slate-400">/ {r.voyage}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-0.5 font-mono text-xs font-bold text-status-green">
                      <CheckCircle2 aria-hidden="true" size={13} /> {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 font-mono text-xs text-slate-500">
                      <Anchor aria-hidden="true" size={13} /> {r.hold ? 'HOLD' : 'NO HOLD'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  )
}
