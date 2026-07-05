import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertTriangle, Bot, CheckCircle2, PhoneCall, Play, Radio,
  Package, DollarSign, Activity, ShieldAlert, ArrowRight,
} from 'lucide-react'

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

// status -> {dot, pill classes} for the light theme
const STATUS_TONE: Record<string, { dot: string; pill: string; label?: string }> = {
  moving: { dot: 'bg-neutral-400', pill: 'bg-neutral-100 text-neutral-600' },
  diagnosing: { dot: 'bg-amber-500', pill: 'bg-amber-50 text-amber-700' },
  stalled: { dot: 'bg-red-500', pill: 'bg-red-50 text-red-700' },
  stalled_unlocatable: { dot: 'bg-red-500', pill: 'bg-red-50 text-red-700', label: 'unlocatable' },
  awaiting_action: { dot: 'bg-orange-500', pill: 'bg-orange-50 text-orange-700', label: 'awaiting approval' },
  executing: { dot: 'bg-blue-500 animate-pulse', pill: 'bg-blue-50 text-blue-700' },
  verifying: { dot: 'bg-blue-500 animate-pulse', pill: 'bg-blue-50 text-blue-700' },
  resolving: { dot: 'bg-emerald-500', pill: 'bg-emerald-50 text-emerald-700' },
  released: { dot: 'bg-emerald-500', pill: 'bg-emerald-50 text-emerald-700' },
  escalated: { dot: 'bg-red-500', pill: 'bg-red-50 text-red-700' },
}

function StatusPill({ status }: { status: string }) {
  const t = STATUS_TONE[status] ?? { dot: 'bg-neutral-400', pill: 'bg-neutral-100 text-neutral-600' }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${t.pill}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${t.dot}`} />
      {t.label ?? status.replace(/_/g, ' ')}
    </span>
  )
}

function artifactUrl(path: string | null): string | null {
  if (!path) return null
  const base = path.split('/').pop()
  return `${ORCH}/artifacts/${base}`
}

type Agent = {
  agent_id: string
  container_id: string
  brain: string
  status: string
  steps: string[]
  interaction_id?: string | null
}

const AGENT_TONE: Record<string, { ring: string; pill: string }> = {
  planning: { ring: 'ring-blue-200', pill: 'bg-blue-50 text-blue-700' },
  awaiting_human: { ring: 'ring-orange-200', pill: 'bg-orange-50 text-orange-700' },
  executing: { ring: 'ring-blue-200', pill: 'bg-blue-50 text-blue-700' },
  done: { ring: 'ring-emerald-200', pill: 'bg-emerald-50 text-emerald-700' },
  failed: { ring: 'ring-red-200', pill: 'bg-red-50 text-red-700' },
}

export function CoordinatorApp() {
  const [containers, setContainers] = useState<Record<string, Container>>({})
  const [agents, setAgents] = useState<Record<string, Agent>>({})
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
        } else if (msg.type === 'agent_spawned') {
          setAgents((prev) => ({
            ...prev,
            [msg.agent_id]: {
              agent_id: msg.agent_id, container_id: msg.container_id,
              brain: msg.brain, status: 'planning', steps: [],
            },
          }))
        } else if (msg.type === 'agent_step') {
          setAgents((prev) => {
            const cur = prev[msg.agent_id] ?? {
              agent_id: msg.agent_id, container_id: msg.container_id, brain: '', steps: [],
            }
            const steps = cur.steps[cur.steps.length - 1] === msg.summary
              ? cur.steps
              : [...cur.steps, msg.summary]
            return {
              ...prev,
              [msg.agent_id]: {
                ...cur, status: msg.status, steps,
                interaction_id: msg.interaction_id ?? cur.interaction_id,
              } as Agent,
            }
          })
        } else if (msg.type === 'agent_done') {
          setAgents((prev) =>
            prev[msg.agent_id]
              ? { ...prev, [msg.agent_id]: { ...prev[msg.agent_id], status: msg.status } }
              : prev,
          )
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
  const activeAgents = useMemo(
    () => Object.values(agents).sort((a, b) => a.container_id.localeCompare(b.container_id)),
    [agents],
  )

  // KPI strip
  const kpi = useMemo(() => {
    const open = rows.filter((c) => c.status !== 'moving' && c.status !== 'released')
    const atRisk = open.reduce((s, c) => s + (c.free_time?.dollars_at_risk ?? 0), 0)
    const working = activeAgents.filter((a) => a.status === 'planning' || a.status === 'executing').length
    const gates = rows.filter((c) => c.pending_action).length
    return { stuck: open.length, atRisk, working, gates }
  }, [rows, activeAgents])

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-neutral-900 antialiased">
      {/* App bar */}
      <header className="sticky top-0 z-10 border-b border-neutral-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-neutral-900 text-white">
              <Package size={17} />
            </div>
            <div className="leading-tight">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-neutral-400">Unblock</p>
              <h1 className="text-[15px] font-semibold tracking-tight">Site Office</h1>
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${connected ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'}`}>
              <Radio size={12} className={connected ? 'animate-pulse' : ''} /> {connected ? 'live' : 'reconnecting'}
            </span>
            {/* DEMO-ONLY controls: normally the alert engine + telephony drive these */}
            <button onClick={() => post('/monitor/tick', {})} className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 shadow-sm transition-colors hover:bg-neutral-50">
              <Play size={14} /> Run tick
            </button>
            <button onClick={() => post('/events/call', { demo: true, container_id: 'MSKU4471' })} className="inline-flex items-center gap-1.5 rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700">
              <PhoneCall size={14} /> Driver calls in
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {/* KPI strip */}
        <section className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi icon={<Package size={16} />} tint="text-neutral-500 bg-neutral-100" label="Stuck containers" value={String(kpi.stuck)} />
          <Kpi icon={<DollarSign size={16} />} tint="text-amber-600 bg-amber-50" label="At risk" value={`$${kpi.atRisk.toFixed(0)}`} />
          <Kpi icon={<Activity size={16} />} tint="text-blue-600 bg-blue-50" label="Agents working" value={String(kpi.working)} />
          <Kpi icon={<ShieldAlert size={16} />} tint="text-orange-600 bg-orange-50" label="Awaiting approval" value={String(kpi.gates)} />
        </section>

        {/* THE single surfaced line + one-tap gate (§7 / §10) */}
        {surfaced && surfaced.pending_action && (
          <section className="mb-6 overflow-hidden rounded-xl border border-orange-200 bg-white shadow-sm">
            <div className="h-1 w-full bg-gradient-to-r from-orange-400 to-amber-400" />
            <div className="flex items-start gap-3.5 p-5">
              <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-orange-50 text-orange-600">
                <AlertTriangle size={18} />
              </div>
              <div className="flex-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-orange-600">Human approval required</p>
                <p className="mt-1 text-lg font-semibold tracking-tight text-neutral-900">{surfaced.pending_action.line}</p>
                <div className="mt-4 flex gap-2.5">
                  <button
                    onClick={() => post('/approve', { container_id: surfaced.id, action_id: surfaced.pending_action!.action_id })}
                    className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-500"
                  >
                    {surfaced.pending_action.goal} <ArrowRight size={15} />
                  </button>
                  <button
                    onClick={() => post('/dismiss', { container_id: surfaced.id, alert_id: `OVERDUE:${surfaced.id}:gate_out` })}
                    className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-50"
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
          <section className="mb-6 overflow-hidden rounded-xl border border-blue-200 bg-white shadow-sm">
            <div className="flex items-center gap-2 border-b border-neutral-100 bg-blue-50/50 px-5 py-2.5">
              <PhoneCall size={14} className="animate-pulse text-blue-600" />
              <p className="text-[11px] font-semibold uppercase tracking-wider text-blue-700">Driver on the line · Live Translate</p>
            </div>
            <div className="space-y-2.5 p-5">
              {transcript.length === 0 && <p className="text-sm italic text-neutral-400">connecting…</p>}
              {transcript.map((t, i) => (
                <div key={i} className={`flex ${t.speaker === 'agent' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-sm ${t.speaker === 'agent' ? 'bg-blue-600 text-white' : 'bg-neutral-100 text-neutral-800'}`}>
                    <span className={`mb-0.5 block text-[10px] font-medium uppercase tracking-wide ${t.speaker === 'agent' ? 'text-blue-200' : 'text-neutral-400'}`}>{t.speaker}</span>
                    {t.text}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Agents at work — the orchestrator spawns one solver agent per stuck container */}
        {activeAgents.length > 0 && (
          <section className="mb-6">
            <p className="mb-2.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-neutral-400">
              <Bot size={14} /> Agents at work
            </p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {activeAgents.map((a) => {
                const tone = AGENT_TONE[a.status] ?? { ring: 'ring-neutral-200', pill: 'bg-neutral-100 text-neutral-600' }
                return (
                  <div key={a.agent_id} className={`rounded-xl border border-neutral-200 bg-white p-4 shadow-sm ring-1 ${tone.ring}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm font-semibold text-neutral-900">{a.container_id}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${tone.pill}`}>{a.status.replace(/_/g, ' ')}</span>
                    </div>
                    <p className="mt-0.5 font-mono text-[10px] text-neutral-400">{a.agent_id} · {a.brain}</p>
                    {a.interaction_id && (
                      <p className="mt-1.5 inline-flex items-center gap-1 rounded-md bg-neutral-100 px-1.5 py-0.5 font-mono text-[10px] text-neutral-500" title={`Reasoning held server-side; resumable by id\n${a.interaction_id}`}>
                        ⛓ durable via Antigravity
                      </p>
                    )}
                    {/* live step timeline — what the agent is doing, in order */}
                    <ol className="mt-3 space-y-1.5">
                      {a.steps.map((s, i) => (
                        <li key={i} className={`flex gap-2 text-sm ${i === a.steps.length - 1 ? 'text-neutral-800' : 'text-neutral-400'}`}>
                          <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-500" />
                          <span>{s}</span>
                        </li>
                      ))}
                      {a.status === 'planning' && (
                        <li className="flex items-center gap-2 text-sm text-neutral-400">
                          <span className="flex gap-0.5">
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400 [animation-delay:-0.3s]" />
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400 [animation-delay:-0.15s]" />
                            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400" />
                          </span>
                          <span className="italic">thinking</span>
                        </li>
                      )}
                    </ol>
                  </div>
                )
              })}
            </div>
          </section>
        )}

        {/* The board — one row per container, sorted by $ at risk */}
        <section className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
          <div className="border-b border-neutral-100 px-5 py-3">
            <h2 className="text-sm font-semibold tracking-tight text-neutral-900">Exception board</h2>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="bg-neutral-50 text-[11px] uppercase tracking-wider text-neutral-400">
              <tr>
                <th className="px-5 py-2.5 font-medium">Container</th>
                <th className="px-5 py-2.5 font-medium">Lane</th>
                <th className="px-5 py-2.5 font-medium">Status</th>
                <th className="px-5 py-2.5 font-medium">$ at risk</th>
                <th className="px-5 py-2.5 font-medium">Blocker</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr><td colSpan={6} className="px-5 py-10 text-center text-sm text-neutral-400">No containers yet — run a tick or take a call.</td></tr>
              )}
              {rows.map((c) => {
                const binding = c.blockers[c.blockers.length - 1]
                return (
                  <Fragment key={c.id}>
                    <tr className="border-t border-neutral-100 transition-colors hover:bg-neutral-50/70">
                      <td className="px-5 py-3 font-mono font-semibold text-neutral-900">{c.id}</td>
                      <td className="px-5 py-3 text-neutral-500">{c.carrier} · {c.port}</td>
                      <td className="px-5 py-3"><StatusPill status={c.status} /></td>
                      <td className="px-5 py-3 font-mono tabular-nums text-neutral-700">{c.free_time?.dollars_at_risk ? `$${c.free_time.dollars_at_risk.toFixed(0)}` : '—'}</td>
                      <td className="px-5 py-3 text-neutral-600">
                        {binding ? (
                          <span className="inline-flex items-center gap-2">
                            {binding.evidence}
                            {binding.discovered_via === 'voice' && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                                <PhoneCall size={10} /> voice
                              </span>
                            )}
                          </span>
                        ) : (
                          <span className="text-neutral-300">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button onClick={() => setExpanded(expanded === c.id ? null : c.id)} className="font-mono text-xs text-neutral-400 transition-colors hover:text-neutral-700">
                          {expanded === c.id ? 'hide' : 'audit'} ({c.action_log.length})
                        </button>
                      </td>
                    </tr>
                    {expanded === c.id && (
                      <tr className="bg-neutral-50/60">
                        <td colSpan={6} className="px-5 py-4">
                          <p className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
                            <CheckCircle2 size={12} /> Audit trail — demurrage-dispute evidence
                          </p>
                          <ol className="space-y-2">
                            {c.action_log.map((e, i) => (
                              <li key={i} className="flex items-start gap-3 text-xs">
                                <span className="w-16 shrink-0 rounded-md bg-white px-1.5 py-0.5 text-center font-mono text-neutral-500 ring-1 ring-neutral-200">{e.actor}</span>
                                <span className="flex-1 text-neutral-600">{e.action} <span className="text-neutral-400">→ {e.result}</span></span>
                                {artifactUrl(e.artifact_path) && (
                                  <a href={artifactUrl(e.artifact_path)!} target="_blank" rel="noreferrer">
                                    <img src={artifactUrl(e.artifact_path)!} alt="screenshot" className="h-9 w-14 rounded-md object-cover ring-1 ring-neutral-200 transition-transform hover:scale-105" />
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

function Kpi({ icon, tint, label, value }: { icon: ReactNode; tint: string; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${tint}`}>{icon}</span>
        <span className="text-xs font-medium uppercase tracking-wide text-neutral-400">{label}</span>
      </div>
      <p className="mt-2.5 text-2xl font-semibold tabular-nums tracking-tight text-neutral-900">{value}</p>
    </div>
  )
}
