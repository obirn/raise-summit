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
      },
    },
  },
  plugins: [react()],
})
