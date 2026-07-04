import { useCallback, useMemo, useState } from 'react'
import {
  createCustomsRequirement,
  ensureCustomsRequirementsInitialized,
  formatCustomsRequirementUpload,
  PRIMARY_CUSTOMS_CONTAINER_ID,
  resetCustomsRequirements,
  saveCustomsRequirements,
  type NewCustomsRequirementInput,
} from '../lib/customsRequirementsStorage'
import type { CustomsRequirement } from '../types'

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.addEventListener('load', () => resolve(String(reader.result ?? '')))
    reader.addEventListener('error', () => reject(reader.error))
    reader.readAsDataURL(file)
  })
}

export function useCustomsRequirements() {
  const [requirements, setRequirements] = useState<CustomsRequirement[]>(
    ensureCustomsRequirementsInitialized,
  )

  const addRequirement = useCallback(
    (input: NewCustomsRequirementInput) => {
      if (!input.title.trim()) {
        return false
      }

      setRequirements((current) => {
        const next = [...current, createCustomsRequirement(input)]
        saveCustomsRequirements(next)
        return next
      })
      return true
    },
    [],
  )

  const uploadRequirementDocument = useCallback(
    async (id: string, file: File) => {
      const uploadedDocumentDataUrl = await readFileAsDataUrl(file)

      setRequirements((current) => {
        const next = current.map((requirement) =>
          requirement.id === id
            ? {
                ...requirement,
                ...formatCustomsRequirementUpload(file),
                uploadedDocumentDataUrl,
              }
            : requirement,
        )

        saveCustomsRequirements(next)
        return next
      })
    },
    [],
  )

  const resetRequirements = useCallback(() => {
    setRequirements(resetCustomsRequirements())
  }, [])

  const primaryContainerRequirements = useMemo(
    () =>
      requirements.filter(
        (requirement) => requirement.containerId === PRIMARY_CUSTOMS_CONTAINER_ID,
      ),
    [requirements],
  )

  const primaryRequirementsAccepted =
    primaryContainerRequirements.length > 0 &&
    primaryContainerRequirements.every((requirement) => Boolean(requirement.uploadedDocumentName))

  return {
    addRequirement,
    primaryContainerRequirements,
    primaryRequirementsAccepted,
    requirements,
    resetRequirements,
    uploadRequirementDocument,
  }
}
