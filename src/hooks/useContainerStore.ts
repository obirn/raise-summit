import { useCallback, useState } from 'react'
import {
  clearContainers,
  DEFAULT_READY_STATUS,
  ensureContainersInitialized,
  formatAuditTimestamp,
  PRIMARY_CONTAINER_ID,
  saveContainers,
} from '../lib/containerStorage'
import type { ContainerRecord } from '../types'

export type NewContainerInput = {
  containerId: string
  bookingRef: string
  vgmWeight: string
  sealNumber: string
  carrierVessel: string
  operationalStatus: string
  customerName: string
  originPort: string
  destinationPort: string
  eta: string
}

/**
 * Manages the TMS container grid with immediate localStorage persistence.
 * All mutations auto-save to `docklock_local_containers_v1`.
 */
export function useContainerStore() {
  const [containers, setContainers] = useState<ContainerRecord[]>(ensureContainersInitialized)
  const [selectedContainerId, setSelectedContainerId] = useState(PRIMARY_CONTAINER_ID)
  const [resetMessage, setResetMessage] = useState<string | null>(null)

  const persist = useCallback((next: ContainerRecord[]) => {
    setContainers(next)
    saveContainers(next)
  }, [])

  const addContainer = useCallback(
    (input: NewContainerInput) => {
      const trimmedId = input.containerId.trim().toUpperCase()

      if (!trimmedId) {
        return false
      }

      const nextRecord: ContainerRecord = {
        containerId: trimmedId,
        bookingRef: input.bookingRef.trim(),
        vgmWeight: input.vgmWeight.trim(),
        sealNumber: input.sealNumber.trim(),
        carrierVessel: input.carrierVessel.trim(),
        operationalStatus: input.operationalStatus.trim() || DEFAULT_READY_STATUS,
        cargoDescription: 'Manual customs cargo description pending',
        customsHsCode: '950300',
        commodityNotes: 'User-created TMS record; customs dossier should be reviewed manually.',
        customerName: input.customerName.trim() || 'Manual TMS Job',
        houseBill: `HBL-${trimmedId.slice(-4)}`,
        masterBill: `MBL-${input.bookingRef.trim() || 'MANUAL'}`,
        originPort: input.originPort.trim() || 'NLRTM Rotterdam',
        destinationPort: input.destinationPort.trim() || 'BEANR Antwerp',
        finalDelivery: 'Docklock QA Yard',
        incoterm: 'DAP',
        transportMode: 'FCL',
        etd: formatAuditTimestamp().slice(1, 11),
        eta: input.eta.trim() || '2026-07-08',
        docsStatus: '[ DOCS: USER ENTERED ]',
        customsEntry: '[ ICS2: PENDING ]',
        terminalStatus: '[ TERMINAL: AWAITING REF ]',
        freightStatus: '[ FREIGHT: CHECK REQUIRED ]',
        releaseInstruction: '[ RELEASE: MANUAL REVIEW ]',
        auditLogs: [],
      }

      persist([...containers, nextRecord])
      setSelectedContainerId(trimmedId)
      return true
    },
    [containers, persist],
  )

  const updateOperationalStatus = useCallback(
    (containerId: string, operationalStatus: string) => {
      const trimmedStatus = operationalStatus.trim()

      if (!trimmedStatus) {
        return false
      }

      persist(
        containers.map((container) =>
          container.containerId === containerId
            ? { ...container, operationalStatus: trimmedStatus }
            : container,
        ),
      )
      return true
    },
    [containers, persist],
  )

  const appendAuditLog = useCallback(
    (containerId: string, note: string) => {
      const trimmedNote = note.trim()

      if (!trimmedNote) {
        return false
      }

      const formattedEntry = `${formatAuditTimestamp()} ${trimmedNote}`

      persist(
        containers.map((container) =>
          container.containerId === containerId
            ? { ...container, auditLogs: [...container.auditLogs, formattedEntry] }
            : container,
        ),
      )
      return true
    },
    [containers, persist],
  )

  const resetToDefaults = useCallback(() => {
    const defaults = clearContainers()
    setContainers(defaults)
    setSelectedContainerId(PRIMARY_CONTAINER_ID)
    setResetMessage('Local sandbox reset to default state.')

    window.setTimeout(() => {
      setResetMessage(null)
    }, 4000)
  }, [])

  const selectedContainer =
    containers.find((container) => container.containerId === selectedContainerId) ?? containers[0]

  return {
    appendAuditLog,
    addContainer,
    containers,
    resetMessage,
    resetToDefaults,
    selectedContainer,
    selectedContainerId,
    setSelectedContainerId,
    updateOperationalStatus,
  }
}
