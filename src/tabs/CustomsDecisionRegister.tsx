import { CheckCircle2, Landmark, XCircle } from 'lucide-react'

// Compact, CU-readable customs decision board. This is the portal "truth" the
// agent reads to rule customs in/out: MSKU4471 is RELEASED (clean, golden path),
// while TCLU3380 carries the screen-only HS-code hold (the decoy). The
// interactive HS-validation sandbox lives below this in CustomsICS2.

type CustomsDecision = {
  containerId: string
  hsCode: string
  status: 'RELEASED' | 'HOLD'
  reason?: string
}

const DECISIONS: CustomsDecision[] = [
  { containerId: 'MSKU4471', hsCode: '950300', status: 'RELEASED' },
  { containerId: 'TCLU3380', hsCode: '870899', status: 'HOLD', reason: 'HS code invalid' },
]

export function CustomsDecisionRegister() {
  return (
    <section className="mx-auto mb-4 max-w-5xl rounded-md border border-slate-300 bg-white p-4 shadow-dock">
      <header className="mb-3 flex items-center gap-2">
        <Landmark aria-hidden="true" size={18} className="text-carrier-navy" />
        <h2 className="font-mono text-xs font-black uppercase tracking-[0.16em] text-slate-500">
          ICS2 Customs Decision Register
        </h2>
      </header>
      <table className="w-full text-left text-sm">
        <thead className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
          <tr>
            <th className="py-1">Container</th>
            <th className="py-1">HS Code</th>
            <th className="py-1">Decision</th>
            <th className="py-1">Note</th>
          </tr>
        </thead>
        <tbody>
          {DECISIONS.map((d) => (
            <tr
              key={d.containerId}
              data-field="customs_row"
              data-container={d.containerId}
              data-status={d.status === 'RELEASED' ? 'released' : 'hold'}
              data-reason={d.reason ?? ''}
              className="border-t border-slate-100"
            >
              <td className="py-2 font-mono font-bold">{d.containerId}</td>
              <td className="py-2 font-mono text-slate-600">{d.hsCode}</td>
              <td className="py-2">
                {d.status === 'RELEASED' ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-0.5 font-mono text-xs font-bold text-status-green">
                    <CheckCircle2 aria-hidden="true" size={13} /> RELEASED
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-0.5 font-mono text-xs font-bold text-status-red">
                    <XCircle aria-hidden="true" size={13} /> HOLD
                  </span>
                )}
              </td>
              <td className="py-2 text-slate-500">{d.reason ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
