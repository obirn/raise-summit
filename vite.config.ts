import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  build: {
    rollupOptions: {
      input: {
        customs: resolve(__dirname, 'index.html'),
        tms: resolve(__dirname, 'tms.html'),
        ui: resolve(__dirname, 'ui.html'),
        carrier: resolve(__dirname, 'carrier.html'),
        terminal: resolve(__dirname, 'terminal.html'),
      },
    },
  },
  plugins: [react()],
})
