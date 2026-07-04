import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, PhoneCall, Play, Radio } from 'lucide-react'

// The orchestrator is the ONLY interface this UI uses (MASTER_PROMPT §3).
const ORCH = (import.meta as { env?: Record<string, string> }).env?.VITE_ORCH_URL ?? 'http://localhost:5000'
const WS_URL = ORCH.replace(/^http/, 'ws') + '/board/stream'

type AuditEntry = {
  ts: string
  actor: string
  action: string
  target_system: string | null
  artifact_path: string | null
  result: string
}
type PendingAction = { action_id: string; goal: string; line: string; cost_class: string }
type Blocker = { type: string; evidence: string; discovered_via: string; reference: string | null }
type FreeTime = { dollars_at_risk: number; free_expires_at: string; liable_party: string }
type Container = {
  id: string
  carrier: string
  port: string
  status: string
  free_time: FreeTime | null
  blockers: Blocker[]
  action_log: AuditEntry[]
  pending_action: PendingAction | null
}

const STATUS_TONE: Record<string, string> = {
  moving: 'bg-slate-100 text-slate-700 border-slate-300',
  diagnosing: 'bg-amber-50 text-amber-800 border-amber-300',
  stalled: 'bg-red-50 text-red-800 border-red-300',
  stalled_unlocatable: 'bg-red-100 text-red-900 border-red-400',
  awaiting_action: 'bg-orange-100 text-orange-900 border-orange-400',
  executing: 'bg-blue-50 text-blue-800 border-blue-300',
  verifying: 'bg-blue-50 text-blue-800 border-blue-300',
  resolving: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  released: 'bg-emerald-100 text-emerald-900 border-emerald-400',
  escalated: 'bg-red-100 text-red-900 border-red-400',
}

function artifactUrl(path: string | null): string | null {
  if (!path) return null
  const base = path.split('/').pop()
  return `${ORCH}/artifacts/${base}`
}

export function CoordinatorApp() {
  const [containers, setContainers] = useState<Record<string, Container>>({})
  const [connected, setConnected] = useState(false)
  const [driverOnLine, setDriverOnLine] = useState(false)
  const [transcript, setTranscript] = useState<{ speaker: string; text: string }[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let closed = false
    function connect() {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws
      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!closed) setTimeout(connect, 1000)
      }
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'board_update') {
          const c: Container = msg.container
          setContainers((prev) => ({ ...prev, [c.id]: c }))
        } else if (msg.type === 'call_started') {
          setDriverOnLine(true)
          setTranscript([])
        } else if (msg.type === 'transcript') {
          setTranscript((prev) => [...prev, { speaker: msg.speaker, text: msg.text }])
        } else if (msg.type === 'resolved') {
          setDriverOnLine(false)
        }
      }
    }
    connect()
    return () => {
      closed = true
      wsRef.current?.close()
    }
  }, [])

  const post = useCallback((path: string, body: unknown) => {
    return fetch(`${ORCH}${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
  }, [])

  const rows = useMemo(
    () =>
      Object.values(containers).sort(
        (a, b) => (b.free_time?.dollars_at_risk ?? 0) - (a.free_time?.dollars_at_risk ?? 0),
      ),
    [containers],
  )
  const surfaced = rows.find((c) => c.pending_action)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/80 px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-slate-500">Unblock</p>
            <h1 className="text-2xl font-black">Site Office</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-xs ${connected ? 'border-emerald-500 text-emerald-400' : 'border-red-500 text-red-400'}`}>
              <Radio size={12} /> {connected ? 'live' : 'reconnecting'}
            </span>
            {/* DEMO-ONLY controls: normally the alert engine + telephony drive these */}
            <button onClick={() => post('/monitor/tick', {})} className="inline-flex items-center gap-1.5 rounded-md border border-slate-600 px-3 py-1.5 text-sm font-semibold hover:bg-slate-800">
              <Play size={14} /> Run tick
            </button>
            <button onClick={() => post('/events/call', { demo: true, container_id: 'MSKU4471' })} className="inline-flex items-center gap-1.5 rounded-md border border-cyan-600 bg-cyan-950 px-3 py-1.5 text-sm font-semibold text-cyan-200 hover:bg-cyan-900">
              <PhoneCall size={14} /> Driver calls in
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {/* THE single surfaced line + one-tap gate (§7 / §10) */}
        {surfaced && surfaced.pending_action && (
          <section className="mb-6 rounded-xl border border-orange-500 bg-orange-950/40 p-5 shadow-dock">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 shrink-0 text-orange-400" />
              <div className="flex-1">
                <p className="font-mono text-[11px] uppercase tracking-widest text-orange-400">Human approval required</p>
                <p className="mt-1 text-lg font-bold text-orange-50">{surfaced.pending_action.line}</p>
                <div className="mt-4 flex gap-3">
                  <button
                    onClick={() => post('/approve', { container_id: surfaced.id, action_id: surfaced.pending_action!.action_id })}
                    className="rounded-md bg-emerald-500 px-5 py-2.5 font-bold text-emerald-950 hover:bg-emerald-400"
                  >
                    {surfaced.pending_action.goal}
                  </button>
                  <button
                    onClick={() => post('/dismiss', { container_id: surfaced.id, alert_id: `OVERDUE:${surfaced.id}:gate_out` })}
                    className="rounded-md border border-slate-600 px-5 py-2.5 font-semibold text-slate-300 hover:bg-slate-800"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Driver on the line + live translated transcript */}
        {driverOnLine && (
          <section className="mb-6 rounded-xl border border-cyan-700 bg-cyan-950/30 p-4">
            <p className="flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-cyan-300">
              <PhoneCall size={13} className="animate-pulse" /> Driver on the line · Live Translate
            </p>
            <div className="mt-3 space-y-1.5 font-mono text-sm">
              {transcript.map((t, i) => (
                <p key={i} className={t.speaker === 'agent' ? 'text-cyan-200' : 'text-slate-300'}>
                  <span className="opacity-60">[{t.speaker}]</span> {t.text}
                </p>
              ))}
            </div>
          </section>
        )}

        {/* The board — one row per container, sorted by $ at risk */}
        <section className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 font-mono text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3">Container</th>
                <th className="px-4 py-3">Lane</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">$ at risk</th>
                <th className="px-4 py-3">Blocker</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => {
                const binding = c.blockers[c.blockers.length - 1]
                return (
                  <Fragment key={c.id}>
                    <tr className="border-t border-slate-800 hover:bg-slate-900/50">
                      <td className="px-4 py-3 font-mono font-bold">{c.id}</td>
                      <td className="px-4 py-3 text-slate-400">{c.carrier} · {c.port}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded-full border px-2.5 py-0.5 font-mono text-[11px] ${STATUS_TONE[c.status] ?? 'bg-slate-100 text-slate-700'}`}>
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono">{c.free_time?.dollars_at_risk ? `$${c.free_time.dollars_at_risk.toFixed(0)}` : '—'}</td>
                      <td className="px-4 py-3 text-slate-300">
                        {binding ? (
                          <span>
                            {binding.evidence}
                            {binding.discovered_via === 'voice' && (
                              <span className="ml-2 rounded bg-cyan-900 px-1.5 py-0.5 font-mono text-[10px] text-cyan-200">via voice</span>
                            )}
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => setExpanded(expanded === c.id ? null : c.id)} className="font-mono text-xs text-slate-400 hover:text-slate-200">
                          {expanded === c.id ? 'hide' : 'audit'} ({c.action_log.length})
                        </button>
                      </td>
                    </tr>
                    {expanded === c.id && (
                      <tr className="bg-slate-900/60">
                        <td colSpan={6} className="px-4 py-4">
                          <p className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-500">
                            <CheckCircle2 size={12} /> Audit trail — demurrage-dispute evidence
                          </p>
                          <ol className="space-y-2">
                            {c.action_log.map((e, i) => (
                              <li key={i} className="flex items-start gap-3 font-mono text-xs">
                                <span className="w-16 shrink-0 rounded bg-slate-800 px-1.5 py-0.5 text-center text-slate-400">{e.actor}</span>
                                <span className="flex-1 text-slate-300">{e.action} <span className="text-slate-600">→ {e.result}</span></span>
                                {artifactUrl(e.artifact_path) && (
                                  <a href={artifactUrl(e.artifact_path)!} target="_blank" rel="noreferrer">
                                    <img src={artifactUrl(e.artifact_path)!} alt="screenshot" className="h-8 w-12 rounded border border-slate-700 object-cover" />
                                  </a>
                                )}
                              </li>
                            ))}
                          </ol>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  )
}
