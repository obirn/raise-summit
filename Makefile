# Unblock — one-command demo control (see CLAUDE.md).
# Targets delegate to scripts/ which activate the Python venv + Node (nvm).
SHELL := /usr/bin/env bash
.PHONY: setup demo demo-cu golden reset kill resume test build lint cu-smoke

setup:  ## install Python + Node deps + Playwright Chromium
	. scripts/env.sh && pip install -q -r requirements.txt && \
	  python -m playwright install chromium && npm install --no-audit --no-fund

demo:   ## boot portals + orchestrator + coordinator UI (stub CU)
	bash scripts/demo.sh

demo-cu: ## same as demo but with REAL Gemini Computer Use (needs GEMINI_API_KEY + display)
	CU_MODE=real bash scripts/demo.sh

cu-smoke: ## one live CU read of the terminal portal (needs the Vite server running)
	. scripts/env.sh && python scripts/cu_smoke.py

golden: ## drive the golden path 1->9 (incl. live kill/resume) via the public API
	bash scripts/golden.sh

reset:  ## wipe board DB + artifacts + browser profile and re-seed deterministically
	. scripts/env.sh && rm -f "$$BOARD_DB_PATH" && rm -rf "$$ARTIFACTS_DIR" "$$CU_PROFILE_DIR" && \
	  python -c "from agent.board.board import Board; from seed.scenario import seed_board, DEMO_NOW; seed_board(Board(), DEMO_NOW); print('re-seeded', Board().all().__len__(), 'containers')"

kill:   ## stop the orchestrator mid-run (proves invariant 4 with `resume`)
	- pkill -f "agent.orchestrator.app" && echo "orchestrator killed"

resume: ## restart the orchestrator; it re-hydrates the board from SQLite
	. scripts/env.sh && uvicorn agent.orchestrator.app:app --host 0.0.0.0 --port "$$ORCH_PORT"

test:   ## unit + integration acceptance tests (§12), no network
	. scripts/env.sh && python -m pytest tests/ -q

build:  ## typecheck + build all Vite pages
	. scripts/env.sh && npm run build

lint:   ## oxlint the frontend
	. scripts/env.sh && npm run lint
