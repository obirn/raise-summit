#!/usr/bin/env bash
# Shared environment bootstrap: activate the Python venv and load Node (nvm).
# Sourced by the other scripts so `make` targets get a consistent toolchain.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Python venv (orchestrator + voice bridge)
if [ -d "$REPO_ROOT/.venv" ]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

# Node via nvm (Vite 8 needs Node >= 20; system node may be older)
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  source "$NVM_DIR/nvm.sh"
  nvm use 22 >/dev/null 2>&1 || nvm use --lts >/dev/null 2>&1 || true
fi

export ORCH_PORT="${ORCH_PORT:-5000}"
export VITE_PORT="${VITE_PORT:-5173}"
export BOARD_DB_PATH="${BOARD_DB_PATH:-$REPO_ROOT/board.db}"
export ARTIFACTS_DIR="${ARTIFACTS_DIR:-$REPO_ROOT/artifacts}"
export PORTAL_BASE_URL="${PORTAL_BASE_URL:-http://localhost:$VITE_PORT}"
export CU_PROFILE_DIR="${CU_PROFILE_DIR:-$REPO_ROOT/.cu_profile}"
