export type TmsStatus = 'DOCUMENTS HOLD' | 'PENDING RELEASE' | 'TRUE RELEASE'
export type CarrierStatus = 'NO HOLD' | 'HOLD'
export type CustomsStatus = 'PENDING' | 'REJECTED' | 'RELEASED'

export type SandboxState = {
  tms_status: TmsStatus
  carrier_status: CarrierStatus
  customs_status: CustomsStatus
  customs_hs_code: string
  terminal_invoice_paid: boolean
}

export type TabKey = 'tms' | 'carrier' | 'customs' | 'terminal'

export type CustomsRequirementCategory =
  | 'Document'
  | 'Data'
  | 'Inspection'
  | 'Payment'
  | 'Other'

export type CustomsRequirementStatus = 'OPEN' | 'SUBMITTED' | 'ACCEPTED' | 'REJECTED'

export type CustomsRequirement = {
  id: string
  containerId: string
  title: string
  category: CustomsRequirementCategory
  status: CustomsRequirementStatus
  details: string
  createdAt: string
  uploadedDocumentName?: string
  uploadedDocumentType?: string
  uploadedDocumentSize?: number
  uploadedDocumentDataUrl?: string
  uploadedAt?: string
}

/** Local container record persisted in browser localStorage for the TMS grid. */
export type ContainerRecord = {
  containerId: string
  bookingRef: string
  vgmWeight: string
  sealNumber: string
  carrierVessel: string
  operationalStatus: string
  cargoDescription?: string
  customsHsCode?: string
  commodityNotes?: string
  customerName?: string
  houseBill?: string
  masterBill?: string
  originPort?: string
  destinationPort?: string
  finalDelivery?: string
  incoterm?: string
  transportMode?: string
  etd?: string
  eta?: string
  docsStatus?: string
  customsEntry?: string
  terminalStatus?: string
  freightStatus?: string
  releaseInstruction?: string
  auditLogs: string[]
}
