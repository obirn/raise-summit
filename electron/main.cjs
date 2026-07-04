const { app, BrowserWindow } = require('electron')
const path = require('node:path')

const devServerUrl = process.env.TMS_DEV_SERVER_URL

function createWindow() {
  const window = new BrowserWindow({
    title: 'Docklock TMS Desktop',
    width: 1440,
    height: 960,
    minWidth: 1120,
    minHeight: 720,
    backgroundColor: '#f1f5f9',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  if (devServerUrl) {
    window.loadURL(`${devServerUrl}/tms.html`)
    window.webContents.openDevTools({ mode: 'detach' })
    return
  }

  window.loadFile(path.join(__dirname, '..', 'dist', 'tms.html'))
}

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
