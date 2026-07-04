import { FileText, Pencil, Plus, Printer, RotateCcw, Save, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useContainerStore } from '../hooks/useContainerStore'
import {
  DEFAULT_READY_STATUS,
  DEFAULT_RELEASE_STATUS,
  PRIMARY_CONTAINER_ID,
} from '../lib/containerStorage'
import type { ContainerRecord, SandboxState } from '../types'

type TMSDashboardProps = {
  state: SandboxState
}

const sidebarGroups = [
  {
    title: 'Forwarding',
    links: [
      'Shipment Register',
      'Bookings',
      'Consols',
      'Containers',
    ],
  },
  {
    title: 'Customs & Docs',
    links: [
      'Customs Entries',
      'Document Packs',
      'EDI Messages',
    ],
  },
  {
    title: 'Operations',
    links: [
      'Carrier Events',
      'Terminal Gate',
      'Accounting Holds',
    ],
  },
]

const registerColumns = [
  'Sel',
  'Container',
  'Job / Booking',
  'Customer',
  'HBL',
  'MBL',
  'Mode',
  'Origin',
  'Destination',
  'Final Delivery',
  'ETD',
  'ETA',
  'VGM',
  'Seal',
  'Carrier / Vessel',
  'Docs',
  'Customs',
  'Terminal',
  'Freight',
  'Operational Status',
  'Action',
]

const toolbarButtons = [
  ['Find', Search],
  ['Docs', FileText],
  ['Print', Printer],
  ['Save View', Save],
] as const

const emptyJobForm = {
  containerId: '',
  bookingRef: '',
  vgmWeight: '',
  sealNumber: '',
  carrierVessel: '',
  operationalStatus: DEFAULT_READY_STATUS,
  customerName: '',
  originPort: '',
  destinationPort: '',
  eta: '',
}

function value(record: ContainerRecord | undefined, field: keyof ContainerRecord, fallback = '-') {
  const content = record?.[field]

  return typeof content === 'string' && content.trim() ? content : fallback
}

function statusTone(status: string) {
  if (/TRUE RELEASE|COMPLETE|ACCEPTED|PREPAID|GATED OUT|READY/i.test(status)) {
    return 'bg-emerald-50 text-emerald-900'
  }

  if (/HOLD|MISSING|BLOCKED|REVIEW|OPEN|NOT SUBMITTED/i.test(status)) {
    return 'bg-red-50 text-red-900'
  }

  return 'bg-yellow-50 text-yellow-900'
}

function frozenColumnClass(index: number) {
  if (index === 0) {
    return 'sticky left-0 z-20 w-9 min-w-9 max-w-9 overflow-hidden shadow-[1px_0_0_#94a3b8]'
  }

  if (index === 1) {
    return 'sticky left-9 z-20 w-24 min-w-24 max-w-24 overflow-hidden shadow-[1px_0_0_#94a3b8]'
  }

  if (index === 2) {
    return 'sticky left-[8.25rem] z-20 w-32 min-w-32 max-w-32 overflow-hidden shadow-[1px_0_0_#94a3b8]'
  }

  if (index === 3) {
    return 'sticky left-[16.25rem] z-20 w-48 min-w-48 max-w-48 overflow-hidden shadow-[1px_0_0_#94a3b8]'
  }

  return ''
}

export function TMSDashboard({ state }: TMSDashboardProps) {
  const isReleased = state.tms_status === 'TRUE RELEASE'
  const {
    appendAuditLog,
    addContainer,
    containers,
    resetMessage,
    resetToDefaults,
    selectedContainer,
    selectedContainerId,
    setSelectedContainerId,
    updateOperationalStatus,
  } = useContainerStore()

  const [showNewJobForm, setShowNewJobForm] = useState(false)
  const [newJobForm, setNewJobForm] = useState(emptyJobForm)
  const [editingContainerId, setEditingContainerId] = useState<string | null>(null)
  const [statusDraft, setStatusDraft] = useState(DEFAULT_READY_STATUS)
  const [manualNote, setManualNote] = useState('')

  const selectedSummary = useMemo(
    () => selectedContainer?.containerId ?? PRIMARY_CONTAINER_ID,
    [selectedContainer],
  )

  const headerFields = [
    ['File No', value(selectedContainer, 'containerId', PRIMARY_CONTAINER_ID)],
    ['Booking', value(selectedContainer, 'bookingRef')],
    ['Client', value(selectedContainer, 'customerName', 'Docklock QA Imports BV')],
    ['House Bill', value(selectedContainer, 'houseBill')],
    ['Master Bill', value(selectedContainer, 'masterBill')],
    ['Mode', value(selectedContainer, 'transportMode', 'FCL')],
    ['Origin', value(selectedContainer, 'originPort')],
    ['Destination', value(selectedContainer, 'destinationPort')],
    ['Final Delivery', value(selectedContainer, 'finalDelivery')],
    ['Incoterm', value(selectedContainer, 'incoterm')],
    ['ETD', value(selectedContainer, 'etd')],
    ['ETA', value(selectedContainer, 'eta')],
  ]

  function handleSaveNewJob() {
    const saved = addContainer(newJobForm)

    if (!saved) {
      return
    }

    setNewJobForm(emptyJobForm)
    setShowNewJobForm(false)
  }

  function startStatusEdit(containerId: string, currentStatus: string) {
    setEditingContainerId(containerId)
    setStatusDraft(currentStatus)
  }

  function saveStatusEdit(containerId: string) {
    if (updateOperationalStatus(containerId, statusDraft)) {
      setEditingContainerId(null)
    }
  }

  function handleAppendNote() {
    if (!selectedContainer) {
      return
    }

    if (appendAuditLog(selectedContainer.containerId, manualNote)) {
      setManualNote('')
    }
  }

  return (
    <section className="overflow-hidden border border-slate-600 bg-tms-gray font-sans text-[13px] shadow-dock">
      {resetMessage ? (
        <div
          aria-live="polite"
          className="border-b border-emerald-700 bg-emerald-100 px-3 py-1.5 text-xs font-bold text-emerald-950"
        >
          {resetMessage}
        </div>
      ) : null}

      <div className="border-b border-slate-700 bg-[#d3d3d3]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-500 px-3 py-1">
          <div className="font-bold text-slate-950">CargoWise One - Forwarding Operations</div>
          <div className="font-mono text-[11px] text-slate-700">
            Company: Docklock Logistics BV | Branch: RTM | User: QA_SANDBOX
          </div>
        </div>

        <div className="flex flex-wrap border-b border-slate-500 bg-[#efefef] text-[12px] font-semibold text-blue-900">
          {['File', 'Edit', 'View', 'Actions', 'Documents', 'Customs', 'Accounting', 'Warehouse', 'Tools', 'Help'].map(
            (item) => (
              <button
                key={item}
                type="button"
                className="border-r border-slate-300 px-3 py-1 hover:bg-white"
              >
                {item}
              </button>
            ),
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1 bg-[#f7f7f7] px-3 py-2">
          {toolbarButtons.map(([label, Icon]) => (
            <button
              key={label}
              type="button"
              className="inline-flex h-8 items-center gap-1 border border-slate-500 bg-white px-2 text-[12px] font-bold text-slate-800 hover:bg-blue-50"
            >
              <Icon aria-hidden="true" size={14} />
              {label}
            </button>
          ))}
          <button
            type="button"
            className="ml-0 inline-flex h-8 items-center gap-1 border border-blue-700 bg-[#eaf2ff] px-2 text-[12px] font-black text-blue-950 hover:bg-white md:ml-3"
            onClick={() => setShowNewJobForm((open) => !open)}
          >
            <Plus aria-hidden="true" size={14} />
            [New Forwarding Job]
          </button>
          <button
            type="button"
            className="inline-flex h-8 items-center gap-1 border border-slate-500 bg-white px-2 text-[12px] font-bold text-slate-800 hover:bg-slate-50"
            onClick={resetToDefaults}
          >
            <RotateCcw aria-hidden="true" size={14} />
            [Reset Local Sandbox Data]
          </button>
          <p className="ml-auto font-mono text-[11px] font-semibold text-slate-600">
            {containers.length} records | docklock_local_containers_v1
          </p>
        </div>
      </div>

      <div className="grid min-h-[760px] grid-cols-1 lg:grid-cols-[230px_1fr]">
        <aside className="border-b border-slate-600 bg-[#d9d9d9] lg:border-b-0 lg:border-r">
          <div className="border-b border-slate-600 bg-[#c8c8c8] px-3 py-2 text-xs font-black uppercase text-slate-700">
            Navigator
          </div>
          <div className="space-y-3 p-2">
            {sidebarGroups.map((group) => (
              <div key={group.title} className="border border-slate-500 bg-[#eeeeee]">
                <div className="border-b border-slate-500 bg-[#cfcfcf] px-2 py-1 text-[11px] font-black uppercase text-slate-700">
                  {group.title}
                </div>
                {group.links.map((item) => (
                  <button
                    key={item}
                    type="button"
                    className="block w-full border-b border-slate-300 bg-[#eef2ff] px-3 py-1.5 text-left text-[12px] font-bold text-blue-900 transition last:border-b-0 hover:bg-white"
                  >
                    {item}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </aside>

        <div className="min-w-0 bg-[#e6e6e6] p-3">
          <div className="mb-2 flex flex-wrap border border-slate-500 bg-[#f6f6f6]">
            {['Job Details', 'Consol', 'Containers', 'Documents', 'Events', 'Accounting'].map(
              (tab, index) => (
                <button
                  key={tab}
                  type="button"
                  className={`border-r border-slate-400 px-4 py-1.5 text-[12px] font-black ${
                    index === 0 ? 'bg-white text-slate-950' : 'bg-[#dddddd] text-slate-700'
                  }`}
                >
                  {tab}
                </button>
              ),
            )}
          </div>

          <div className="mb-3 border border-slate-600 bg-white">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-500 bg-[#d7e4f2] px-3 py-2">
              <div>
                <h2 className="text-lg font-black text-slate-950">
                  Forwarding Job Register - {selectedSummary}
                </h2>
                <p className="text-[12px] font-semibold text-slate-700">
                  Shipment operations, EDI, customs and terminal status in one TMS file.
                </p>
              </div>
              <div
                className={`border-2 px-3 py-1 font-mono text-sm font-black ${
                  isReleased
                    ? 'border-status-green bg-green-100 text-status-green'
                    : 'border-status-red bg-red-100 text-status-red'
                }`}
              >
                {state.tms_status}
              </div>
            </div>

            <div className="grid grid-cols-1 border-b border-slate-500 md:grid-cols-2 xl:grid-cols-4">
              {headerFields.map(([label, content]) => (
                <div key={label} className="grid grid-cols-[112px_1fr] border-b border-r border-slate-300 last:border-r-0">
                  <div className="bg-[#efefef] px-2 py-1 font-bold text-slate-600">{label}</div>
                  <div className="min-w-0 truncate px-2 py-1 font-mono font-semibold text-slate-950">
                    {content}
                  </div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-2 bg-[#f7f7f7] p-2 md:grid-cols-5">
              {[
                ['Carrier Hold', state.carrier_status],
                ['Docs Pack', value(selectedContainer, 'docsStatus')],
                ['Customs State', state.customs_status],
                ['Terminal Gate', state.terminal_invoice_paid ? 'INVOICE PAID' : 'INVOICE OPEN'],
                ['Release Gate', isReleased ? 'OPEN' : 'LOCKED'],
              ].map(([label, content]) => (
                <div
                  key={label}
                  className="border border-slate-500 bg-white px-2 py-2 hover:bg-yellow-50"
                >
                  <p className="text-[10px] font-black uppercase text-slate-500">{label}</p>
                  <p className="truncate font-mono text-[12px] font-black text-slate-950">{content}</p>
                </div>
              ))}
            </div>
          </div>

          {showNewJobForm ? (
            <form
              className="mb-3 border-2 border-blue-400 bg-white"
              onSubmit={(event) => {
                event.preventDefault()
                handleSaveNewJob()
              }}
            >
              <div className="border-b border-blue-300 bg-[#d7e4f2] px-3 py-2 font-black text-blue-950">
                New Forwarding Job Entry
              </div>
              <div className="grid gap-3 p-3 md:grid-cols-2 xl:grid-cols-5">
                {(
                  [
                    ['containerId', 'Container ID', 'TGHU882109'],
                    ['bookingRef', 'Booking Ref', 'BKG-102934'],
                    ['customerName', 'Customer', 'Apex Retail Stores'],
                    ['originPort', 'Origin Port', 'USNYC New York'],
                    ['destinationPort', 'Destination Port', 'NLRTM Rotterdam'],
                    ['eta', 'ETA', '2026-07-08'],
                    ['vgmWeight', 'VGM Weight', '18,500 KG'],
                    ['sealNumber', 'Seal Number', 'US-449102'],
                    ['carrierVessel', 'Carrier / Vessel', 'CMA CGM / 104W'],
                    ['operationalStatus', 'Operational Status', DEFAULT_READY_STATUS],
                  ] as const
                ).map(([field, label, placeholder]) => (
                  <label key={field} className="block text-[12px] font-bold text-slate-700">
                    {label}
                    <input
                      className="mt-1 h-9 w-full border border-slate-400 bg-white px-2 font-mono text-[12px]"
                      placeholder={placeholder}
                      value={newJobForm[field]}
                      onChange={(event) =>
                        setNewJobForm((current) => ({
                          ...current,
                          [field]: event.target.value,
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
              <div className="flex flex-wrap gap-2 border-t border-slate-300 bg-[#f5f5f5] px-3 py-2">
                <button
                  type="submit"
                  className="h-9 border border-carrier-navy bg-carrier-navy px-4 text-[12px] font-black text-white hover:bg-slate-800"
                >
                  [Save Job to Local Grid]
                </button>
                <button
                  type="button"
                  className="h-9 border border-slate-400 bg-white px-4 text-[12px] font-bold text-slate-700 hover:bg-slate-50"
                  onClick={() => {
                    setShowNewJobForm(false)
                    setNewJobForm(emptyJobForm)
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : null}

          <div className="overflow-x-auto border border-slate-600 bg-white">
            <table className="min-w-[1900px] border-separate border-spacing-0 text-left text-[11px]">
              <thead className="bg-[#c9d9ed] text-slate-950">
                <tr>
                  {registerColumns.map((header, index) => (
                    <th
                      key={header}
                      className={`border border-slate-500 px-2 py-1.5 font-black ${
                        index < 4 ? `${frozenColumnClass(index)} z-30 bg-[#c9d9ed]` : ''
                      }`}
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {containers.map((container, index) => {
                  const isSelected = container.containerId === selectedContainerId
                  const isEditing = editingContainerId === container.containerId
                  const frozenBg = isSelected
                    ? 'bg-[#fff2a8]'
                    : index % 2 === 0
                      ? 'bg-white'
                      : 'bg-[#f7f7f7]'

                  return (
                    <tr
                      key={container.containerId}
                      className={`cursor-pointer ${
                        isSelected
                          ? 'bg-[#fff2a8]'
                          : index % 2 === 0
                            ? 'bg-white hover:bg-blue-50'
                            : 'bg-[#f7f7f7] hover:bg-blue-50'
                      }`}
                      onClick={() => setSelectedContainerId(container.containerId)}
                    >
                      <td
                        className={`border border-slate-400 px-2 py-1 text-center font-mono ${frozenColumnClass(0)} ${frozenBg}`}
                      >
                        {isSelected ? '>>' : ''}
                      </td>
                      <td
                        className={`border border-slate-400 px-2 py-1 font-mono font-black ${frozenColumnClass(1)} ${frozenBg}`}
                      >
                        {container.containerId}
                      </td>
                      <td
                        className={`truncate border border-slate-400 px-2 py-1 font-mono ${frozenColumnClass(2)} ${frozenBg}`}
                      >
                        {container.bookingRef}
                      </td>
                      <td
                        className={`truncate border border-slate-400 px-2 py-1 font-semibold ${frozenColumnClass(3)} ${frozenBg}`}
                      >
                        {value(container, 'customerName')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1 font-mono">
                        {value(container, 'houseBill')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1 font-mono">
                        {value(container, 'masterBill')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1">
                        {value(container, 'transportMode')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1">
                        {value(container, 'originPort')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1">
                        {value(container, 'destinationPort')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1">
                        {value(container, 'finalDelivery')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1 font-mono">
                        {value(container, 'etd')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1 font-mono">
                        {value(container, 'eta')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1 font-mono">
                        {container.vgmWeight}
                      </td>
                      <td className="border border-slate-400 px-2 py-1 font-mono">
                        {container.sealNumber}
                      </td>
                      <td className="border border-slate-400 px-2 py-1">
                        {container.carrierVessel}
                      </td>
                      <td className={`border border-slate-400 px-2 py-1 font-mono ${statusTone(value(container, 'docsStatus'))}`}>
                        {value(container, 'docsStatus')}
                      </td>
                      <td className={`border border-slate-400 px-2 py-1 font-mono ${statusTone(value(container, 'customsEntry'))}`}>
                        {value(container, 'customsEntry')}
                      </td>
                      <td className={`border border-slate-400 px-2 py-1 font-mono ${statusTone(value(container, 'terminalStatus'))}`}>
                        {value(container, 'terminalStatus')}
                      </td>
                      <td className={`border border-slate-400 px-2 py-1 font-mono ${statusTone(value(container, 'freightStatus'))}`}>
                        {value(container, 'freightStatus')}
                      </td>
                      <td className="border border-slate-400 px-2 py-1">
                        {isEditing ? (
                          <div
                            className="flex min-w-[240px] flex-col gap-1"
                            onClick={(event) => event.stopPropagation()}
                          >
                            <input
                              className="h-8 w-full border border-slate-400 px-2 font-mono text-[11px]"
                              value={statusDraft}
                              onChange={(event) => setStatusDraft(event.target.value)}
                            />
                            <div className="flex flex-wrap gap-1">
                              <button
                                type="button"
                                className="border border-slate-400 bg-white px-2 py-0.5 text-[10px] font-bold"
                                onClick={() => setStatusDraft(DEFAULT_READY_STATUS)}
                              >
                                Ready
                              </button>
                              <button
                                type="button"
                                className="border border-slate-400 bg-white px-2 py-0.5 text-[10px] font-bold"
                                onClick={() => setStatusDraft(DEFAULT_RELEASE_STATUS)}
                              >
                                True Release
                              </button>
                            </div>
                          </div>
                        ) : (
                          <span className={`font-mono font-bold ${statusTone(container.operationalStatus)}`}>
                            {container.operationalStatus}
                          </span>
                        )}
                      </td>
                      <td
                        className="border border-slate-400 px-2 py-1"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {isEditing ? (
                          <div className="flex gap-1">
                            <button
                              type="button"
                              className="border border-emerald-600 bg-emerald-50 px-2 py-1 text-[11px] font-black text-emerald-900"
                              onClick={() => saveStatusEdit(container.containerId)}
                            >
                              Save
                            </button>
                            <button
                              type="button"
                              className="border border-slate-400 bg-white px-2 py-1 text-[11px] font-bold"
                              onClick={() => setEditingContainerId(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            className="inline-flex items-center gap-1 border border-slate-500 bg-[#eef2ff] px-2 py-1 text-[11px] font-bold text-blue-900 hover:bg-white"
                            onClick={() =>
                              startStatusEdit(container.containerId, container.operationalStatus)
                            }
                          >
                            <Pencil aria-hidden="true" size={12} />
                            [Edit]
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="mt-3 grid gap-3 lg:grid-cols-[1.3fr_0.7fr]">
            <section className="border border-slate-600 bg-white">
              <div className="border-b border-slate-500 bg-[#d7e4f2] px-3 py-2 font-black">
                Customs & Docs Logs - {selectedContainer?.containerId ?? PRIMARY_CONTAINER_ID}
              </div>
              <div className="max-h-56 space-y-2 overflow-y-auto p-3 font-mono text-[12px]">
                {selectedContainer?.auditLogs.length ? (
                  selectedContainer.auditLogs.map((entry, index) => (
                    <p key={`${entry}-${index}`} className="border-b border-slate-200 pb-1">
                      {entry}
                    </p>
                  ))
                ) : (
                  <p className="text-slate-500">No audit entries for this container.</p>
                )}
              </div>
              <div className="border-t border-slate-400 bg-[#f8fafc] p-3">
                <label
                  className="mb-2 block text-[11px] font-black uppercase text-slate-600"
                  htmlFor="manual-edi-note"
                >
                  Append Manual EDI Note / Override:
                </label>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <input
                    id="manual-edi-note"
                    className="h-10 flex-1 border border-slate-400 bg-white px-3 font-mono text-[12px]"
                    placeholder="EDI override note for selected container..."
                    value={manualNote}
                    onChange={(event) => setManualNote(event.target.value)}
                  />
                  <button
                    type="button"
                    className="h-10 border border-carrier-navy bg-carrier-navy px-4 text-[12px] font-black text-white hover:bg-slate-800"
                    onClick={handleAppendNote}
                  >
                    [Save Note to Local Log]
                  </button>
                </div>
              </div>
            </section>

            <section className="border border-slate-600 bg-[#f8fafc]">
              <div className="border-b border-slate-500 bg-[#d7e4f2] px-3 py-2 font-black">
                Release Control
              </div>
              <div className="p-4">
                <p className="text-[11px] font-black uppercase text-slate-600">Current Decision</p>
                <p className="mt-1 text-3xl font-black text-slate-950">
                  {isReleased ? 'TRUE RELEASE' : 'BLOCKED'}
                </p>
                <p className="mt-3 text-sm font-semibold text-slate-700">
                  Customs must be RELEASED and terminal invoice must be PAID before the TMS flag opens.
                </p>
                <div className="mt-4 space-y-2 border-t border-slate-300 pt-4 font-mono text-[12px] text-slate-700">
                  <p>09:42 ICS2 code stored as {state.customs_hs_code || 'EMPTY'}</p>
                  <p>09:57 Carrier reports {state.carrier_status}</p>
                  <p>
                    10:11 Terminal invoice {state.terminal_invoice_paid ? 'closed' : 'awaiting payment'}
                  </p>
                  <p>10:18 TMS release flag reads {state.tms_status}</p>
                  <p>Selected release instruction: {value(selectedContainer, 'releaseInstruction')}</p>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </section>
  )
}
