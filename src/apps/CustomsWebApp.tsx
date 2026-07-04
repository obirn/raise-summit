import { useCustomsRequirements } from '../hooks/useCustomsRequirements'
import { CustomsDecisionRegister } from '../tabs/CustomsDecisionRegister'
import { CustomsICS2 } from '../tabs/CustomsICS2'
import {
  deriveTmsStatus,
  useSandboxState,
  VALID_HS_CODE,
} from '../shared/sandboxState'

export function CustomsWebApp() {
  const { sandbox, setSandbox } = useSandboxState()
  const customsRequirements = useCustomsRequirements()

  function updateHsCode(customs_hs_code: string) {
    setSandbox((current) => ({ ...current, customs_hs_code }))
  }

  function validateCustoms() {
    setSandbox((current) => {
      const customs_status =
        current.customs_hs_code.trim() === VALID_HS_CODE &&
        customsRequirements.primaryRequirementsAccepted
          ? 'RELEASED'
          : 'REJECTED'

      return deriveTmsStatus({ ...current, customs_status })
    })
  }

  return (
    <div className="min-h-screen bg-ics2-paper pt-4">
      <CustomsDecisionRegister />
      <CustomsICS2
        state={sandbox}
        validHsCode={VALID_HS_CODE}
        requirements={customsRequirements.requirements}
        primaryRequirementsAccepted={customsRequirements.primaryRequirementsAccepted}
        onAddRequirement={customsRequirements.addRequirement}
        onHsCodeChange={updateHsCode}
        onResetRequirements={customsRequirements.resetRequirements}
        onRequirementDocumentUpload={customsRequirements.uploadRequirementDocument}
        onValidate={validateCustoms}
      />
    </div>
  )
}
