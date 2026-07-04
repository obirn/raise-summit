import type {
  ContainerRecord,
  CustomsRequirementCategory,
  CustomsRequirementStatus,
} from '../types'

export type SuggestedCustomsRequirement = {
  title: string
  category: CustomsRequirementCategory
  status: CustomsRequirementStatus
  details: string
}

export type ContainerCustomsAssessment = {
  containerId: string
  cargoDescription: string
  hsCode: string
  requiredItems: SuggestedCustomsRequirement[]
  riskLabel: 'READY' | 'NEEDS DOCUMENTS' | 'MANUAL REVIEW'
}

function containsAny(source: string, terms: string[]) {
  return terms.some((term) => source.includes(term))
}

export function assessContainerForCustoms(
  container: ContainerRecord,
): ContainerCustomsAssessment {
  const cargoDescription = container.cargoDescription || 'Cargo description not entered'
  const hsCode = container.customsHsCode || '-'
  const text = `${cargoDescription} ${container.commodityNotes ?? ''}`.toLowerCase()
  const requiredItems: SuggestedCustomsRequirement[] = []

  if (containsAny(text, ['phone', 'bluetooth', 'wireless', 'radio', 'headset'])) {
    requiredItems.push({
      title: 'State radio equipment authorization',
      category: 'Data',
      status: 'OPEN',
      details:
        'Upload import/export authorization from the state authority for Bluetooth, wireless, radio or connected-device equipment.',
    })
  }

  if (containsAny(text, ['lithium', 'battery', 'rechargeable'])) {
    requiredItems.push({
      title: 'Lithium battery transport declaration',
      category: 'Document',
      status: 'OPEN',
      details:
        'Provide battery declaration, packing statement and transport compliance note for rechargeable or lithium-powered goods.',
    })
  }

  if (containsAny(text, ['toy', 'toys', 'children', 'learning tablet'])) {
    requiredItems.push({
      title: 'Toy safety conformity certificate',
      category: 'Document',
      status: 'OPEN',
      details:
        'Provide toy safety conformity evidence and product safety file before release of child-facing goods.',
    })
  }

  if (containsAny(text, ['food', 'plant', 'seed', 'wood', 'phytosanitary'])) {
    requiredItems.push({
      title: 'Phytosanitary or food control certificate',
      category: 'Inspection',
      status: 'OPEN',
      details:
        'Upload sanitary, phytosanitary or food-control certificate for controlled organic goods.',
    })
  }

  return {
    containerId: container.containerId,
    cargoDescription,
    hsCode,
    requiredItems,
    riskLabel:
      requiredItems.length > 0
        ? 'NEEDS DOCUMENTS'
        : cargoDescription === 'Cargo description not entered'
          ? 'MANUAL REVIEW'
          : 'READY',
  }
}
