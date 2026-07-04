import { AlertTriangle, CheckCircle2, Landmark, Plus, RotateCcw, ShieldQuestion } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useContainerStore } from '../hooks/useContainerStore'
import {
  CUSTOMS_REQUIREMENT_CATEGORIES,
  PRIMARY_CUSTOMS_CONTAINER_ID,
  type NewCustomsRequirementInput,
} from '../lib/customsRequirementsStorage'
import { assessContainerForCustoms } from '../lib/customsRuleEngine'
import type {
  CustomsRequirement,
  SandboxState,
} from '../types'

type CustomsICS2Props = {
  onAddRequirement: (input: NewCustomsRequirementInput) => boolean
  onHsCodeChange: (value: string) => void
  onRequirementDocumentUpload: (id: string, file: File) => void
  onResetRequirements: () => void
  onValidate: () => void
  primaryRequirementsAccepted: boolean
  requirements: CustomsRequirement[]
  state: SandboxState
  validHsCode: string
}

const emptyRequirementForm: NewCustomsRequirementInput = {
  containerId: PRIMARY_CUSTOMS_CONTAINER_ID,
  title: '',
  category: 'Document',
  status: 'OPEN',
  details: '',
}

function documentStatusClasses(requirement: CustomsRequirement) {
  if (requirement.uploadedDocumentName) {
    return 'border-status-green bg-green-50 text-status-green'
  }

  return 'border-status-red bg-red-50 text-status-red'
}

function formatBytes(size?: number) {
  if (!size) {
    return ''
  }

  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`
  }

  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

export function CustomsICS2({
  onAddRequirement,
  onHsCodeChange,
  onRequirementDocumentUpload,
  onResetRequirements,
  onValidate,
  primaryRequirementsAccepted,
  requirements,
  state,
  validHsCode,
}: CustomsICS2Props) {
  const { containers } = useContainerStore()
  const [showRequirementForm, setShowRequirementForm] = useState(false)
  const [requirementForm, setRequirementForm] = useState(emptyRequirementForm)
  const [selectedReviewContainerId, setSelectedReviewContainerId] = useState(
    PRIMARY_CUSTOMS_CONTAINER_ID,
  )
  const released = state.customs_status === 'RELEASED'
  const rejected = state.customs_status === 'REJECTED'
  const hsCodeValid = state.customs_hs_code.trim() === validHsCode
  const blockedByRequirements = rejected && hsCodeValid && !primaryRequirementsAccepted

  const groupedRequirements = useMemo(() => {
    return requirements.reduce<Record<string, CustomsRequirement[]>>((groups, requirement) => {
      const key = requirement.containerId
      groups[key] = [...(groups[key] ?? []), requirement]
      return groups
    }, {})
  }, [requirements])

  const primaryRequirements = groupedRequirements[PRIMARY_CUSTOMS_CONTAINER_ID] ?? []
  const acceptedCount = primaryRequirements.filter(
    (requirement) => requirement.uploadedDocumentName,
  ).length
  const containerAssessments = useMemo(
    () => containers.map((container) => assessContainerForCustoms(container)),
    [containers],
  )
  const selectedAssessment =
    containerAssessments.find(
      (assessment) => assessment.containerId === selectedReviewContainerId,
    ) ?? containerAssessments[0]

  function handleSaveRequirement() {
    const saved = onAddRequirement(requirementForm)

    if (!saved) {
      return
    }

    setRequirementForm(emptyRequirementForm)
    setShowRequirementForm(false)
  }

  function requirementExists(containerId: string, title: string) {
    return requirements.some(
      (requirement) => requirement.containerId === containerId && requirement.title === title,
    )
  }

  function handleCreateSuggestedRequirements(containerId: string) {
    const assessment = containerAssessments.find((item) => item.containerId === containerId)

    if (!assessment) {
      return
    }

    assessment.requiredItems.forEach((item) => {
      if (requirementExists(containerId, item.title)) {
        return
      }

      onAddRequirement({
        containerId,
        title: item.title,
        category: item.category,
        status: 'OPEN',
        details: item.details,
      })
    })
  }

  return (
    <section className="min-h-[620px] border border-slate-300 bg-ics2-shell p-5 shadow-dock">
      <div className="mb-5 border-b border-slate-300 bg-ics2-paper p-4">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-sm bg-carrier-navy text-white">
              <Landmark aria-hidden="true" size={24} />
            </div>
            <div>
              <p className="font-mono text-xs font-black uppercase tracking-[0.18em] text-slate-500">
                Customs ICS2 Portal
              </p>
              <h2 className="text-3xl font-black text-slate-950">Entry Summary Declaration</h2>
            </div>
          </div>
          <div
            className={`rounded-sm border px-5 py-3 text-xl font-black ${
              released
                ? 'border-status-green bg-green-50 text-status-green'
                : rejected
                  ? 'border-status-red bg-red-50 text-status-red'
                  : 'border-status-amber bg-orange-50 text-status-amber'
            }`}
          >
            {state.customs_status}
          </div>
        </div>
      </div>

      <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <form
            className="min-w-0 border border-slate-300 bg-ics2-paper p-5"
            onSubmit={(event) => {
              event.preventDefault()
              onValidate()
            }}
          >
            <div className="mb-4 flex min-w-0 flex-col justify-between gap-3 border-b border-slate-300 pb-3 md:flex-row md:items-center">
              <div>
                <p className="font-mono text-xs font-black uppercase tracking-[0.16em] text-slate-500">
                  ENS control reference
                </p>
                <p className="font-black text-slate-950">MSKU4471 / Declaration dossier</p>
              </div>
              <div className="max-w-full break-words border border-slate-400 bg-white px-3 py-2 font-mono text-xs font-black">
                Documents: {acceptedCount}/{primaryRequirements.length} UPLOADED
              </div>
            </div>

            <label className="block text-sm font-black uppercase text-slate-600" htmlFor="hs-code">
              Customs HS Code
            </label>
            <input
              id="hs-code"
              value={state.customs_hs_code}
              className="mt-2 h-12 w-full border border-slate-400 bg-white px-3 font-mono text-lg font-bold text-slate-950"
              inputMode="numeric"
              onChange={(event) => onHsCodeChange(event.target.value)}
            />

            {rejected && !blockedByRequirements ? (
              <div className="mt-4 flex min-w-0 gap-3 border border-status-red bg-red-50 p-3 text-status-red">
                <AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
                <p className="min-w-0 break-words font-bold">
                  ICS2 validation rejected. HS code must be {validHsCode} before downstream release can clear.
                </p>
              </div>
            ) : null}

            {blockedByRequirements ? (
              <div className="mt-4 flex min-w-0 gap-3 border border-status-red bg-red-50 p-3 text-status-red">
                <AlertTriangle aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
                <p className="min-w-0 break-words font-bold">
                  ICS2 validation rejected. Requirements incomplete for {PRIMARY_CUSTOMS_CONTAINER_ID}; every required document must be uploaded before release.
                </p>
              </div>
            ) : null}

            {released ? (
              <div className="mt-4 flex min-w-0 gap-3 border border-status-green bg-green-50 p-3 text-status-green">
                <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
                <p className="min-w-0 break-words font-bold">
                  ICS2 declaration released. Terminal invoice state is now the remaining release prerequisite.
                </p>
              </div>
            ) : null}

            <button
              type="submit"
              className="mt-5 h-12 rounded-sm bg-carrier-navy px-5 font-black text-white hover:bg-slate-800"
            >
              Validate & Re-submit
            </button>
          </form>

          <section className="min-w-0 overflow-hidden border border-slate-300 bg-ics2-paper">
            <div className="border-b border-slate-300 bg-[#DDE8F4] px-4 py-3">
              <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
                <div>
                  <p className="font-mono text-xs font-black uppercase tracking-[0.16em] text-slate-500">
                    Container Intelligence Queue
                  </p>
                  <h3 className="text-xl font-black text-slate-950">
                    Cargo controls and missing authorization checks
                  </h3>
                </div>
                <div className="flex items-center gap-2 border border-slate-400 bg-white px-3 py-2 text-xs font-bold text-slate-700">
                  <ShieldQuestion aria-hidden="true" size={16} />
                  Sandbox rules, not legal advice
                </div>
              </div>
            </div>

            <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_320px]">
              <div className="max-w-full overflow-x-auto">
                <table className="min-w-[940px] w-full border-collapse text-left text-sm">
                  <thead className="bg-[#DDE8F4] text-slate-700">
                    <tr>
                      {[
                        'Container',
                        'Customer',
                        'Cargo / Goods',
                        'HS',
                        'Decision',
                        'Required by rule',
                        'Action',
                      ].map((header) => (
                        <th key={header} className="border border-slate-300 px-3 py-2">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {containers.map((container) => {
                      const assessment = containerAssessments.find(
                        (item) => item.containerId === container.containerId,
                      )
                      const missingCount =
                        assessment?.requiredItems.filter(
                          (item) => !requirementExists(container.containerId, item.title),
                        ).length ?? 0

                      return (
                        <tr
                          key={container.containerId}
                          className={
                            selectedReviewContainerId === container.containerId
                              ? 'bg-blue-50'
                              : 'bg-white'
                          }
                        >
                          <td className="border border-slate-200 px-3 py-2 font-mono font-black">
                            {container.containerId}
                          </td>
                          <td className="border border-slate-200 px-3 py-2">
                            {container.customerName ?? '-'}
                          </td>
                          <td className="border border-slate-200 px-3 py-2">
                            {container.cargoDescription ?? 'Cargo description not entered'}
                          </td>
                          <td className="border border-slate-200 px-3 py-2 font-mono">
                            {assessment?.hsCode ?? '-'}
                          </td>
                          <td className="border border-slate-200 px-3 py-2">
                            <span
                              className={`inline-flex border px-2 py-1 text-xs font-black ${
                                assessment?.riskLabel === 'READY'
                                  ? 'border-status-green bg-green-50 text-status-green'
                                  : assessment?.riskLabel === 'MANUAL REVIEW'
                                    ? 'border-status-amber bg-orange-50 text-status-amber'
                                    : 'border-status-red bg-red-50 text-status-red'
                              }`}
                            >
                              {assessment?.riskLabel ?? 'MANUAL REVIEW'}
                            </span>
                          </td>
                          <td className="border border-slate-200 px-3 py-2">
                            {assessment?.requiredItems.length ? (
                              <ul className="list-inside list-disc space-y-1">
                                {assessment.requiredItems.map((item) => (
                                  <li key={item.title}>{item.title}</li>
                                ))}
                              </ul>
                            ) : (
                              <span className="font-semibold text-status-green">
                                No extra rule-generated documents.
                              </span>
                            )}
                          </td>
                          <td className="border border-slate-200 px-3 py-2">
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                className="border border-slate-500 bg-white px-2 py-1 text-xs font-bold text-slate-800 hover:bg-blue-50"
                                onClick={() => setSelectedReviewContainerId(container.containerId)}
                              >
                                Review
                              </button>
                              {missingCount > 0 ? (
                                <button
                                  type="button"
                                  className="border border-carrier-navy bg-carrier-navy px-2 py-1 text-xs font-black text-white hover:bg-slate-800"
                                  onClick={() =>
                                    handleCreateSuggestedRequirements(container.containerId)
                                  }
                                >
                                  Create {missingCount} item{missingCount === 1 ? '' : 's'}
                                </button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <aside className="border border-slate-300 bg-white p-4">
                <p className="font-mono text-xs font-black uppercase tracking-[0.16em] text-slate-500">
                  Officer prompt
                </p>
                <h4 className="mt-1 text-lg font-black text-slate-950">
                  {selectedAssessment?.containerId ?? PRIMARY_CUSTOMS_CONTAINER_ID}
                </h4>
                <p className="mt-3 text-sm font-semibold text-slate-700">
                  {selectedAssessment?.cargoDescription ?? 'Cargo description not entered'}
                </p>
                <div className="mt-4 space-y-2 text-sm">
                  {selectedAssessment?.requiredItems.length ? (
                    selectedAssessment.requiredItems.map((item) => (
                      <div key={item.title} className="border border-slate-200 bg-[#F8FBFF] p-3">
                        <p className="font-black text-slate-950">{item.title}</p>
                        <p className="mt-1 text-slate-700">{item.details}</p>
                        <p className="mt-2 font-mono text-xs font-bold text-status-red">
                          Question: has this authorization/document been uploaded and accepted?
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="border border-green-200 bg-green-50 p-3 font-bold text-status-green">
                      This container is ready under the current sandbox rules.
                    </p>
                  )}
                </div>
              </aside>
            </div>
          </section>

          <section className="min-w-0 overflow-hidden border border-slate-300 bg-ics2-paper">
            <div className="flex flex-col justify-between gap-3 border-b border-slate-300 bg-[#DDE8F4] px-4 py-3 md:flex-row md:items-center">
              <div>
                <p className="font-mono text-xs font-black uppercase tracking-[0.16em] text-slate-500">
                  Local Dossier Requirements
                </p>
                <h3 className="text-xl font-black text-slate-950">
                  Container-linked requirement register
                </h3>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 border border-slate-500 bg-white px-3 text-xs font-black text-slate-800 hover:bg-blue-50"
                  onClick={() => setShowRequirementForm((open) => !open)}
                >
                  <Plus aria-hidden="true" size={15} />
                  [+ Add Requirement]
                </button>
                <button
                  type="button"
                  className="inline-flex h-9 items-center gap-2 border border-slate-500 bg-white px-3 text-xs font-bold text-slate-700 hover:bg-blue-50"
                  onClick={onResetRequirements}
                >
                  <RotateCcw aria-hidden="true" size={15} />
                  Reset ICS2 Dossier
                </button>
              </div>
            </div>

            {showRequirementForm ? (
              <form
                className="grid gap-3 border-b border-slate-300 bg-white p-4 md:grid-cols-2"
                onSubmit={(event) => {
                  event.preventDefault()
                  handleSaveRequirement()
                }}
              >
                <label className="text-sm font-bold text-slate-700">
                  Container ID
                  <input
                    className="mt-1 h-10 w-full border border-slate-400 px-3 font-mono text-sm"
                    value={requirementForm.containerId}
                    onChange={(event) =>
                      setRequirementForm((current) => ({
                        ...current,
                        containerId: event.target.value.toUpperCase(),
                      }))
                    }
                  />
                </label>
                <label className="text-sm font-bold text-slate-700">
                  Title
                  <input
                    className="mt-1 h-10 w-full border border-slate-400 px-3 text-sm"
                    placeholder="Requirement title"
                    value={requirementForm.title}
                    onChange={(event) =>
                      setRequirementForm((current) => ({
                        ...current,
                        title: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="text-sm font-bold text-slate-700">
                  Category
                  <select
                    className="mt-1 h-10 w-full border border-slate-400 bg-white px-3 text-sm"
                    value={requirementForm.category}
                    onChange={(event) =>
                      setRequirementForm((current) => ({
                        ...current,
                        category: event.target.value as NewCustomsRequirementInput['category'],
                      }))
                    }
                  >
                    {CUSTOMS_REQUIREMENT_CATEGORIES.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="md:col-span-2 text-sm font-bold text-slate-700">
                  Details
                  <textarea
                    className="mt-1 min-h-20 w-full border border-slate-400 px-3 py-2 text-sm"
                    placeholder="Requirement information for the local customs dossier"
                    value={requirementForm.details}
                    onChange={(event) =>
                      setRequirementForm((current) => ({
                        ...current,
                        details: event.target.value,
                      }))
                    }
                  />
                </label>
                <div className="flex gap-2 md:col-span-2">
                  <button
                    type="submit"
                    className="h-10 border border-carrier-navy bg-carrier-navy px-4 text-sm font-black text-white hover:bg-slate-800"
                  >
                    Save Requirement
                  </button>
                  <button
                    type="button"
                    className="h-10 border border-slate-400 bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50"
                    onClick={() => {
                      setRequirementForm(emptyRequirementForm)
                      setShowRequirementForm(false)
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : null}

            <div className="divide-y divide-slate-200">
              {Object.entries(groupedRequirements).map(([containerId, containerRequirements]) => (
                <div key={containerId} className="p-4">
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <h4 className="font-mono text-sm font-black text-slate-950">
                      Container {containerId}
                    </h4>
                    <span className="border border-slate-400 bg-white px-2 py-1 font-mono text-xs font-bold">
                      {containerRequirements.filter((item) => item.uploadedDocumentName).length}/
                      {containerRequirements.length} UPLOADED
                    </span>
                  </div>
                  <div className="max-w-full overflow-x-auto">
                    <table className="min-w-[760px] w-full border-collapse text-left text-sm">
                      <thead className="bg-[#DDE8F4] text-slate-700">
                        <tr>
                          {['Requirement', 'Category', 'Document upload', 'Details', 'Created'].map(
                            (header) => (
                              <th key={header} className="border border-slate-300 px-3 py-2">
                                {header}
                              </th>
                            ),
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {containerRequirements.map((requirement) => (
                          <tr key={requirement.id} className="bg-white">
                            <td className="border border-slate-200 px-3 py-2 font-bold">
                              {requirement.title}
                            </td>
                            <td className="border border-slate-200 px-3 py-2">
                              {requirement.category}
                            </td>
                            <td className="border border-slate-200 px-3 py-2">
                              <div className="min-w-[220px] space-y-2">
                                <div
                                  className={`border px-2 py-1 text-xs font-black ${documentStatusClasses(requirement)}`}
                                >
                                  {requirement.uploadedDocumentName
                                    ? 'DOCUMENT UPLOADED'
                                    : 'UPLOAD REQUIRED'}
                                </div>
                                <input
                                  aria-label={`Upload document for ${requirement.title}`}
                                  className="w-full text-xs"
                                  type="file"
                                  onChange={(event) => {
                                    const file = event.target.files?.[0]

                                    if (file) {
                                      onRequirementDocumentUpload(requirement.id, file)
                                    }
                                  }}
                                />
                                {requirement.uploadedDocumentName ? (
                                  <p className="font-mono text-[11px] font-bold text-slate-700">
                                    {requirement.uploadedDocumentName}
                                    {formatBytes(requirement.uploadedDocumentSize)
                                      ? ` · ${formatBytes(requirement.uploadedDocumentSize)}`
                                      : ''}
                                    {requirement.uploadedAt ? ` · ${requirement.uploadedAt}` : ''}
                                  </p>
                                ) : null}
                              </div>
                            </td>
                            <td className="border border-slate-200 px-3 py-2">
                              {requirement.details}
                            </td>
                            <td className="border border-slate-200 px-3 py-2 font-mono text-xs">
                              {requirement.createdAt}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="min-w-0 border border-slate-300 bg-white p-5">
          <p className="font-mono text-xs font-black uppercase tracking-[0.16em] text-slate-500">
            Declaration Snapshot
          </p>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between border-b border-slate-200 pb-2">
              <dt className="font-bold text-slate-500">Container</dt>
              <dd className="font-mono font-black">{PRIMARY_CUSTOMS_CONTAINER_ID}</dd>
            </div>
            <div className="flex justify-between border-b border-slate-200 pb-2">
              <dt className="font-bold text-slate-500">Requirement gate</dt>
              <dd
                className={`font-mono font-black ${
                  primaryRequirementsAccepted ? 'text-status-green' : 'text-status-red'
                }`}
              >
                {primaryRequirementsAccepted ? 'COMPLETE' : 'INCOMPLETE'}
              </dd>
            </div>
            <div className="flex justify-between border-b border-slate-200 pb-2">
              <dt className="font-bold text-slate-500">Terminal invoice</dt>
              <dd className="font-mono font-black text-carrier-navy">
                {state.terminal_invoice_paid ? 'PAID' : 'OPEN'}
              </dd>
            </div>
            <div className="flex justify-between border-b border-slate-200 pb-2">
              <dt className="font-bold text-slate-500">TMS release</dt>
              <dd className="font-mono font-black text-carrier-navy">
                {state.tms_status}
              </dd>
            </div>
          </dl>
        </aside>
      </div>
    </section>
  )
}
