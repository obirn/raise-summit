/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'tms-gray': '#E0E0E0',
        'carrier-navy': '#0B214A',
        'carrier-cyan': '#00A6D6',
        'ics2-shell': '#EAF1F8',
        'ics2-paper': '#F8FBFF',
        'terminal-slate': '#111827',
        'terminal-panel': '#1F2937',
        'terminal-green': '#5CFF9C',
        'status-green': '#137333',
        'status-red': '#B3261E',
        'status-amber': '#B05C00',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        dock: '0 14px 40px rgba(15, 23, 42, 0.12)',
      },
    },
  },
  plugins: [],
}
