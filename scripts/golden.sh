#!/usr/bin/env bash
# Drive the golden path 1->9 against a running orchestrator via its public API
# only (no backdoor). Proves the live kill/resume in the middle. Requires the
# orchestrator to be up (e.g. `make demo` in another shell) OR boots one.
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

API="http://localhost:$ORCH_PORT"
OWN_SERVER=""

if ! curl -fsS "$API/board" >/dev/null 2>&1; then
  echo "▶ booting orchestrator on $ORCH_PORT"
  uvicorn agent.orchestrator.app:app --host 0.0.0.0 --port "$ORCH_PORT" --log-level warning &
  OWN_SERVER=$!
  for _ in $(seq 1 30); do curl -fsS "$API/board" >/dev/null 2>&1 && break; sleep 0.3; done
fi
cleanup() { [ -n "$OWN_SERVER" ] && kill "$OWN_SERVER" 2>/dev/null || true; }
trap cleanup EXIT

say() { printf '\n\033[1;36m%s\033[0m\n' "$1"; }

say "1-2  monitor tick → diagnose (CU reads, cause on no portal)"
curl -fsS -X POST "$API/monitor/tick" >/dev/null
curl -fsS "$API/board" | python -c "import sys,json;c=[x for x in json.load(sys.stdin) if x['id']=='MSKU4471'][0];print('   MSKU4471:',c['status'])"

say "3-4  driver call (Live Translate) → targeted terminal read reveals \$340"
curl -fsS -X POST "$API/events/call" -H 'content-type: application/json' -d '{"demo":true,"container_id":"MSKU4471"}' >/dev/null
LINE=$(curl -fsS "$API/board" | python -c "import sys,json;c=[x for x in json.load(sys.stdin) if x['id']=='MSKU4471'][0];print(c['pending_action']['line'])")
echo "   surfaced: $LINE"

say "6-8  operator approves → CU pays/releases → verify → callback"
curl -fsS -X POST "$API/approve" -H 'content-type: application/json' -d '{"container_id":"MSKU4471","action_id":"unpaid_detention:MSKU4471"}' >/dev/null
curl -fsS "$API/board" | python -c "import sys,json;c=[x for x in json.load(sys.stdin) if x['id']=='MSKU4471'][0];print('   MSKU4471:',c['status'],'| screenshots:',sum(1 for e in c['action_log'] if e['artifact_path']))"

if [ -n "$OWN_SERVER" ]; then
  say "9    kill → resume (state survives from SQLite)"
  kill "$OWN_SERVER"; OWN_SERVER=""; sleep 1
  uvicorn agent.orchestrator.app:app --host 0.0.0.0 --port "$ORCH_PORT" --log-level warning &
  OWN_SERVER=$!
  for _ in $(seq 1 30); do curl -fsS "$API/board" >/dev/null 2>&1 && break; sleep 0.3; done
  curl -fsS "$API/board" | python -c "import sys,json;c=[x for x in json.load(sys.stdin) if x['id']=='MSKU4471'][0];assert c['status']=='resolving',c['status'];print('   resumed MSKU4471:',c['status'],'— nothing lost ✓')"
fi

say "GOLDEN PATH OK"
