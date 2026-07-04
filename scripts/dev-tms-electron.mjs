import { spawn } from 'node:child_process'
import http from 'node:http'

const host = '127.0.0.1'
const port = Number(process.env.TMS_DEV_PORT ?? 5173)
const devServerUrl = `http://${host}:${port}`

const vite = spawn(
  'npm',
  ['run', 'dev:customs', '--', '--host', host, '--port', String(port), '--strictPort'],
  {
    stdio: 'inherit',
    shell: true,
  },
)

let electron

function waitForVite() {
  http
    .get(`${devServerUrl}/tms.html`, (response) => {
      response.resume()

      if (response.statusCode && response.statusCode < 500) {
        electron = spawn('npx', ['electron', 'electron/main.cjs'], {
          env: { ...process.env, TMS_DEV_SERVER_URL: devServerUrl },
          stdio: 'inherit',
          shell: true,
        })

        electron.on('exit', (code) => {
          vite.kill('SIGTERM')
          process.exit(code ?? 0)
        })
        return
      }

      setTimeout(waitForVite, 250)
    })
    .on('error', () => setTimeout(waitForVite, 250))
}

waitForVite()

process.on('SIGINT', () => {
  electron?.kill('SIGINT')
  vite.kill('SIGINT')
})
