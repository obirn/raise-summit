import { configReleased } from '../shared/sandboxState'
import { TMSDashboard } from '../tabs/TMSDashboard'

export function TmsDesktopApp() {
  return <TMSDashboard state={configReleased} />
}
