import type {
  CustomsRequirement,
  CustomsRequirementCategory,
  CustomsRequirementStatus,
} from '../types'

export const CUSTOMS_REQUIREMENTS_STORAGE_KEY = 'docklock_ics2_requirements_v1'
export const PRIMARY_CUSTOMS_CONTAINER_ID = 'MSKU4471'

export const CUSTOMS_REQUIREMENT_CATEGORIES: CustomsRequirementCategory[] = [
  'Document',
  'Data',
  'Inspection',
  'Payment',
  'Other',
]

export const CUSTOMS_REQUIREMENT_STATUSES: CustomsRequirementStatus[] = [
  'OPEN',
  'SUBMITTED',
  'ACCEPTED',
  'REJECTED',
]

export const DEFAULT_CUSTOMS_REQUIREMENTS: CustomsRequirement[] = [
  {
    id: 'req-commercial-invoice',
    containerId: PRIMARY_CUSTOMS_CONTAINER_ID,
    title: 'Commercial invoice uploaded',
    category: 'Document',
    status: 'OPEN',
    details: 'Invoice value, currency, seller, buyer and line totals must match the ENS declaration.',
    createdAt: '2026-07-04 08:30:00',
  },
  {
    id: 'req-packing-list',
    containerId: PRIMARY_CUSTOMS_CONTAINER_ID,
    title: 'Packing list cross-check',
    category: 'Document',
    status: 'OPEN',
    details: 'Package count and gross weight must reconcile with VGM and TMS shipment file.',
    createdAt: '2026-07-04 08:34:00',
  },
  {
    id: 'req-hs-justification',
    containerId: PRIMARY_CUSTOMS_CONTAINER_ID,
    title: 'HS code justification',
    category: 'Data',
    status: 'OPEN',
    details: 'Declarant must justify HS 950300 against product description before release.',
    createdAt: '2026-07-04 08:39:00',
  },
  {
    id: 'req-ens-reference',
    containerId: PRIMARY_CUSTOMS_CONTAINER_ID,
    title: 'ENS filing reference',
    category: 'Data',
    status: 'OPEN',
    details: 'ENS reference missing carrier acknowledgement number.',
    createdAt: '2026-07-04 08:45:00',
  },
  {
    id: 'req-terminal-proof',
    containerId: PRIMARY_CUSTOMS_CONTAINER_ID,
    title: 'Terminal invoice proof',
    category: 'Payment',
    status: 'OPEN',
    details: 'Proof of terminal invoice closure must be retained for release audit.',
    createdAt: '2026-07-04 08:50:00',
  },
]

export type NewCustomsRequirementInput = {
  containerId: string
  title: string
  category: CustomsRequirementCategory
  status: CustomsRequirementStatus
  details: string
}

function isRequirementCategory(value: unknown): value is CustomsRequirementCategory {
  return (
    typeof value === 'string' &&
    CUSTOMS_REQUIREMENT_CATEGORIES.includes(value as CustomsRequirementCategory)
  )
}

function isRequirementStatus(value: unknown): value is CustomsRequirementStatus {
  return (
    typeof value === 'string' &&
    CUSTOMS_REQUIREMENT_STATUSES.includes(value as CustomsRequirementStatus)
  )
}

function isCustomsRequirement(value: unknown): value is CustomsRequirement {
  if (!value || typeof value !== 'object') {
    return false
  }

  const record = value as CustomsRequirement

  return (
    typeof record.id === 'string' &&
    typeof record.containerId === 'string' &&
    typeof record.title === 'string' &&
    isRequirementCategory(record.category) &&
    isRequirementStatus(record.status) &&
    typeof record.details === 'string' &&
    typeof record.createdAt === 'string' &&
    (record.uploadedDocumentName === undefined ||
      typeof record.uploadedDocumentName === 'string') &&
    (record.uploadedDocumentType === undefined ||
      typeof record.uploadedDocumentType === 'string') &&
    (record.uploadedDocumentSize === undefined ||
      typeof record.uploadedDocumentSize === 'number') &&
    (record.uploadedDocumentDataUrl === undefined ||
      typeof record.uploadedDocumentDataUrl === 'string') &&
    (record.uploadedAt === undefined || typeof record.uploadedAt === 'string')
  )
}

function nowStamp(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0')

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function createId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }

  return `req-${Date.now()}-${Math.round(Math.random() * 10000)}`
}

function hydrateRequirements(requirements: CustomsRequirement[]): CustomsRequirement[] {
  const byId = new Map(
    DEFAULT_CUSTOMS_REQUIREMENTS.map((requirement) => [requirement.id, requirement]),
  )

  requirements.forEach((requirement) => {
    byId.set(requirement.id, {
      ...requirement,
      status: requirement.uploadedDocumentName ? 'ACCEPTED' : 'OPEN',
    })
  })

  return Array.from(byId.values())
}

export function createCustomsRequirement(
  input: NewCustomsRequirementInput,
): CustomsRequirement {
  return {
    id: createId(),
    containerId: input.containerId.trim().toUpperCase() || PRIMARY_CUSTOMS_CONTAINER_ID,
    title: input.title.trim(),
    category: input.category,
    status: 'OPEN',
    details: input.details.trim(),
    createdAt: nowStamp(),
  }
}

export function formatCustomsRequirementUpload(file: File) {
  return {
    uploadedDocumentName: file.name,
    uploadedDocumentType: file.type || 'application/octet-stream',
    uploadedDocumentSize: file.size,
    uploadedAt: nowStamp(),
    status: 'ACCEPTED' as const,
  }
}

export function loadCustomsRequirements(): CustomsRequirement[] {
  try {
    const raw = localStorage.getItem(CUSTOMS_REQUIREMENTS_STORAGE_KEY)

    if (!raw) {
      return [...DEFAULT_CUSTOMS_REQUIREMENTS]
    }

    const parsed: unknown = JSON.parse(raw)

    if (!Array.isArray(parsed) || !parsed.every(isCustomsRequirement)) {
      return [...DEFAULT_CUSTOMS_REQUIREMENTS]
    }

    return hydrateRequirements(parsed)
  } catch {
    return [...DEFAULT_CUSTOMS_REQUIREMENTS]
  }
}

export function saveCustomsRequirements(requirements: CustomsRequirement[]): void {
  localStorage.setItem(CUSTOMS_REQUIREMENTS_STORAGE_KEY, JSON.stringify(requirements))
}

export function resetCustomsRequirements(): CustomsRequirement[] {
  localStorage.removeItem(CUSTOMS_REQUIREMENTS_STORAGE_KEY)
  const defaults = [...DEFAULT_CUSTOMS_REQUIREMENTS]
  saveCustomsRequirements(defaults)
  return defaults
}

export function ensureCustomsRequirementsInitialized(): CustomsRequirement[] {
  const requirements = loadCustomsRequirements()

  saveCustomsRequirements(requirements)

  return requirements
}
