import type { ContainerRecord } from '../types'

/** localStorage key for the TMS container grid sandbox. */
export const CONTAINER_STORAGE_KEY = 'docklock_local_containers_v1'

export const DEFAULT_READY_STATUS = '[ STATUS: READY TO LIFT ]'
export const DEFAULT_RELEASE_STATUS = '[ TRUE RELEASE - NETWORK VERIFIED ]'
export const PRIMARY_CONTAINER_ID = 'MSKU4471'

/** Seed data written when localStorage is empty or reset. */
export const DEFAULT_CONTAINERS: ContainerRecord[] = [
  {
    containerId: PRIMARY_CONTAINER_ID,
    bookingRef: 'BKG-882910',
    vgmWeight: '22,400 KG',
    sealNumber: 'EU-773829',
    carrierVessel: 'Maersk Line / 2603W',
    operationalStatus: DEFAULT_READY_STATUS,
    cargoDescription: 'Smart phones, Bluetooth headsets, wireless charging pads',
    customsHsCode: '950300',
    commodityNotes: 'Contains Bluetooth/radio modules and lithium batteries; sandbox rule requires state authorization before release.',
    customerName: 'Docklock QA Imports BV',
    houseBill: 'HBL-RTM-4471',
    masterBill: 'MAEU-99827144',
    originPort: 'CNSHA Shanghai',
    destinationPort: 'NLRTM Rotterdam',
    finalDelivery: 'Docklock QA Yard 4',
    incoterm: 'DAP',
    transportMode: 'FCL 40HC',
    etd: '2026-06-16',
    eta: '2026-07-04',
    docsStatus: '[ DOCS: PACK LOCKED ]',
    customsEntry: '[ ICS2: HS CODE REVIEW ]',
    terminalStatus: '[ TERMINAL: INVOICE OPEN ]',
    freightStatus: '[ FREIGHT: PREPAID ]',
    releaseInstruction: '[ RELEASE: WAIT CUSTOMS + TERMINAL ]',
    auditLogs: [
      '[2026-07-04 08:14:22] SYSCALL: Internal warehouse packing manifest LOCKED and VERIFIED.',
      '[2026-07-04 09:00:01] EDI_OUT: Transmitting booking BKG-882910 to ocean carrier network...',
      '[2026-07-04 11:32:10] NETWORK_WARN: Downstream tracking notice – Mismatch detected in carrier subsystem. External hold applied on chassis dispatch.',
      '[2026-07-04 11:32:11] SYS_NOTE: TMS local status remains [READY TO LIFT] by warehouse default. Action required: Check external carrier portal.',
    ],
  },
  {
    containerId: 'TCLU3390',
    bookingRef: 'BKG-441205',
    vgmWeight: '19,100 KG',
    sealNumber: 'EU-221004',
    carrierVessel: 'MSC / 1407E',
    operationalStatus: '[ STATUS: ARCHIVED ]',
    cargoDescription: 'Archived textile garments and cotton accessories',
    customsHsCode: '620520',
    commodityNotes: 'Low-risk archived apparel shipment.',
    customerName: 'Northwind Distribution',
    houseBill: 'HBL-HAM-3390',
    masterBill: 'MSCU-77193055',
    originPort: 'TRMER Mersin',
    destinationPort: 'DEHAM Hamburg',
    finalDelivery: 'Northwind DC Bremen',
    incoterm: 'CIF',
    transportMode: 'FCL 20GP',
    etd: '2026-06-28',
    eta: '2026-07-03',
    docsStatus: '[ DOCS: ARCHIVED ]',
    customsEntry: '[ ICS2: CLOSED ]',
    terminalStatus: '[ TERMINAL: GATED OUT ]',
    freightStatus: '[ FREIGHT: CLOSED ]',
    releaseInstruction: '[ RELEASE: COMPLETED ]',
    auditLogs: [
      '[2026-07-03 14:22:00] EDI_OUT: Booking BKG-441205 closed in archive queue.',
    ],
  },
  {
    containerId: 'CAIU7712',
    bookingRef: 'BKG-773410',
    vgmWeight: '24,760 KG',
    sealNumber: 'NL-883104',
    carrierVessel: 'CMA CGM / 104W',
    operationalStatus: '[ STATUS: DOCS HOLD ]',
    cargoDescription: 'Industrial sensor boards with Bluetooth diagnostic modules',
    customsHsCode: '853710',
    commodityNotes: 'Wireless diagnostic modules trigger radio equipment authorization checks.',
    customerName: 'Blue Yard Components',
    houseBill: 'HBL-GDN-7712',
    masterBill: 'CMDU-44019872',
    originPort: 'PLGDN Gdansk',
    destinationPort: 'FRLEH Le Havre',
    finalDelivery: 'Blue Yard Rouen',
    incoterm: 'DDP',
    transportMode: 'FCL 40GP',
    etd: '2026-07-01',
    eta: '2026-07-06',
    docsStatus: '[ DOCS: MISSING COMMERCIAL INVOICE ]',
    customsEntry: '[ ICS2: NOT SUBMITTED ]',
    terminalStatus: '[ TERMINAL: NOT ARRIVED ]',
    freightStatus: '[ FREIGHT: COLLECT ]',
    releaseInstruction: '[ RELEASE: BLOCKED BY DOCS ]',
    auditLogs: [
      '[2026-07-04 07:44:19] DOC_WARN: Commercial invoice value mismatch against packing list.',
      '[2026-07-04 08:03:12] USER_NOTE: Awaiting revised shipper invoice before customs pre-lodgement.',
    ],
  },
  {
    containerId: 'TGHU882109',
    bookingRef: 'BKG-102934',
    vgmWeight: '18,500 KG',
    sealNumber: 'US-449102',
    carrierVessel: 'Hapag-Lloyd / 018E',
    operationalStatus: '[ STATUS: READY TO LIFT ]',
    cargoDescription: 'Retail toys, plastic learning tablets, rechargeable battery packs',
    customsHsCode: '950300',
    commodityNotes: 'Toy safety and lithium battery documents should be present before final release.',
    customerName: 'Apex Retail Stores',
    houseBill: 'HBL-NYC-2109',
    masterBill: 'HLCU-55102938',
    originPort: 'USNYC New York',
    destinationPort: 'NLRTM Rotterdam',
    finalDelivery: 'Apex DC Tilburg',
    incoterm: 'FOB',
    transportMode: 'FCL 40HC',
    etd: '2026-06-20',
    eta: '2026-07-05',
    docsStatus: '[ DOCS: COMPLETE ]',
    customsEntry: '[ ICS2: ACCEPTED ]',
    terminalStatus: '[ TERMINAL: PRE-ADVISED ]',
    freightStatus: '[ FREIGHT: PREPAID ]',
    releaseInstruction: '[ RELEASE: PENDING ARRIVAL ]',
    auditLogs: [
      '[2026-07-04 10:17:45] EDI_IN: Terminal pre-advice accepted for quay appointment.',
      '[2026-07-04 10:18:02] SYS_NOTE: Ready to lift once vessel discharge is confirmed.',
    ],
  },
]

/** Formats a timestamp for audit log entries: [YYYY-MM-DD HH:MM:SS]. */
export function formatAuditTimestamp(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0')

  return `[${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}]`
}

function isContainerRecord(value: unknown): value is ContainerRecord {
  if (!value || typeof value !== 'object') {
    return false
  }

  const record = value as ContainerRecord

  return (
    typeof record.containerId === 'string' &&
    typeof record.bookingRef === 'string' &&
    typeof record.vgmWeight === 'string' &&
    typeof record.sealNumber === 'string' &&
    typeof record.carrierVessel === 'string' &&
    typeof record.operationalStatus === 'string' &&
    Array.isArray(record.auditLogs) &&
    record.auditLogs.every((entry) => typeof entry === 'string')
  )
}

function hydrateContainers(containers: ContainerRecord[]): ContainerRecord[] {
  const defaultsById = new Map(
    DEFAULT_CONTAINERS.map((container) => [container.containerId, container]),
  )

  containers.forEach((container) => {
    const defaultRecord = defaultsById.get(container.containerId)

    defaultsById.set(container.containerId, {
      ...defaultRecord,
      ...container,
      auditLogs: container.auditLogs.length
        ? container.auditLogs
        : (defaultRecord?.auditLogs ?? container.auditLogs),
    })
  })

  return Array.from(defaultsById.values())
}

/** Reads persisted containers or returns the default seed array. */
export function loadContainers(): ContainerRecord[] {
  try {
    const raw = localStorage.getItem(CONTAINER_STORAGE_KEY)

    if (!raw) {
      return [...DEFAULT_CONTAINERS]
    }

    const parsed: unknown = JSON.parse(raw)

    if (!Array.isArray(parsed) || !parsed.every(isContainerRecord)) {
      return [...DEFAULT_CONTAINERS]
    }

    return hydrateContainers(parsed)
  } catch {
    return [...DEFAULT_CONTAINERS]
  }
}

/** Serializes the container array to localStorage. */
export function saveContainers(containers: ContainerRecord[]): void {
  localStorage.setItem(CONTAINER_STORAGE_KEY, JSON.stringify(containers))
}

/** Removes persisted data and returns the default seed array. */
export function clearContainers(): ContainerRecord[] {
  localStorage.removeItem(CONTAINER_STORAGE_KEY)
  const defaults = [...DEFAULT_CONTAINERS]
  saveContainers(defaults)
  return defaults
}

/** Initializes storage on first visit when the key is missing. */
export function ensureContainersInitialized(): ContainerRecord[] {
  const containers = loadContainers()

  saveContainers(containers)

  return containers
}
