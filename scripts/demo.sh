#!/usr/bin/env bash
# Boot everything for the live demo: portals (Vite), orchestrator (FastAPI), UI.
# The board is seeded deterministically on first boot. Ctrl-C tears it all down.
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

# Auto-clean any leftover instance from a previous run BEFORE starting. Repeated
# launches otherwise stack multiple orchestrators (each launches a CU Chromium at
# import, before uvicorn even tries to bind :5000) all fighting over the same
# .cu_profile lock — the #1 cause of "CU frozen / Connection closed". Vite uses
# --strictPort so a duplicate there fails loudly instead of piling up.
echo "▶ clearing any previous orchestrator / CU browser…"
pkill -f "agent.orchestrator.app" 2>/dev/null || true
pkill -f "user-data-dir=.*cu_profile" 2>/dev/null || true
rm -f "$CU_PROFILE_DIR"/Singleton* 2>/dev/null || true
sleep 1

PIDS=()
cleanup() { echo; echo "stopping…"; for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

echo "▶ orchestrator  http://localhost:$ORCH_PORT"
uvicorn agent.orchestrator.app:app --host 0.0.0.0 --port "$ORCH_PORT" --log-level warning &
PIDS+=($!)

echo "▶ portals + UI  http://localhost:$VITE_PORT"
npx vite --host 127.0.0.1 --port "$VITE_PORT" --strictPort &
PIDS+=($!)

sleep 2
echo
echo "════════════════════════════════════════════════════════════"
echo "  Coordinator (Site Office):  http://localhost:$VITE_PORT/ui.html"
echo "  TMS portal:                 http://localhost:$VITE_PORT/tms.html"
echo "  Customs ICS2 portal:        http://localhost:$VITE_PORT/index.html"
echo "  Carrier portal:             http://localhost:$VITE_PORT/carrier.html"
echo "  Terminal gate portal:       http://localhost:$VITE_PORT/terminal.html"
echo "  Orchestrator API:           http://localhost:$ORCH_PORT/board"
echo "════════════════════════════════════════════════════════════"
echo "  In the Site Office: 'Run tick' → 'Driver calls in' → approve."
echo "  Ctrl-C to stop."
wait
