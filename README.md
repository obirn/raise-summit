# Docklock Split Apps

Two focused apps live in this workspace:

- TMS Desktop: React renderer wrapped by Electron.
- Custom ICS2 Web App: Vite React web app served from `index.html`.

## Run

```bash
npm install
npm run dev:customs
```

Open the printed Vite URL to use the Custom ICS2 web app.

```bash
npm run dev:tms
```

Starts Vite and opens the TMS desktop app in Electron.

## Build

```bash
npm run build
npm run desktop:tms
```
