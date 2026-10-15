#!/usr/bin/env bash
set -eu

slice="${1:-all}"
workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
app_root="$workspace_root/sentinelflow"

resolve_uv_bin() {
  if command -v uv >/dev/null 2>&1 && uv --version >/dev/null 2>&1; then
    echo "uv"
    return 0
  fi

  if [[ -x "$HOME/.local/bin/uv" ]] && "$HOME/.local/bin/uv" --version >/dev/null 2>&1; then
    echo "$HOME/.local/bin/uv"
    return 0
  fi

  local user_name="${USERNAME:-${USER:-}}"
  local candidates=()
  if [[ -n "$user_name" ]]; then
    candidates+=(
      "/home/$user_name/.local/bin/uv"
      "/mnt/c/Users/$user_name/.local/bin/uv"
      "/c/Users/$user_name/.local/bin/uv"
      "/mnt/c/Users/$user_name/.local/bin/uv.exe"
      "/c/Users/$user_name/.local/bin/uv.exe"
    )
  fi

  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]] && "$candidate" --version >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

UV_BIN="${UV_BIN:-}"
if [[ -z "$UV_BIN" ]]; then
  if ! UV_BIN="$(resolve_uv_bin)"; then
    echo "Unable to find uv executable. Install uv or set UV_BIN." >&2
    exit 127
  fi
fi

resolve_node_bin() {
  if command -v node >/dev/null 2>&1 && node --version >/dev/null 2>&1; then
    echo "node"
    return 0
  fi
  local candidates=(
    "/c/Program Files/nodejs/node.exe"
    "/mnt/c/Program Files/nodejs/node.exe"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]] && "$candidate" --version >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

NODE_BIN="${NODE_BIN:-}"
if [[ -z "$NODE_BIN" ]]; then
  if ! NODE_BIN="$(resolve_node_bin)"; then
    NODE_BIN="node"
  fi
fi

run_backend() {
  echo "[sentinelflow] backend: uv sync --extra dev && uv run ruff check app && uv run pytest && uv run python -m app.evals.run"
  (
    cd "$app_root/backend"
    "$UV_BIN" sync --extra dev
    "$UV_BIN" run ruff check app
    "$UV_BIN" run pytest
    "$UV_BIN" run python -m app.evals.run
  )
}

run_frontend() {
  echo "[sentinelflow] frontend: pnpm install && pnpm test && pnpm build"
  (
    cd "$app_root/frontend"
    pnpm install
    pnpm test
    pnpm build
  )
}

run_contract_check() {
  echo "[sentinelflow] contract: verifying OpenAPI and TypeScript contract synchronization"
  (
    cd "$app_root/frontend"
    "$NODE_BIN" scripts/generate-types.js
  )
  (
    cd "$workspace_root"
    git diff --exit-code sentinelflow/backend/openapi.json sentinelflow/frontend/lib/types/api.generated.ts
  )
}

case "$slice" in
  backend)
    run_backend
    ;;
  frontend)
    run_frontend
    ;;
  contract|contracts)
    run_contract_check
    ;;
  all|cross-stack|crossstack)
    run_backend
    run_contract_check
    run_frontend
    ;;
  *)
    echo "Usage: $0 [backend|frontend|contract|all]" >&2
    exit 2
    ;;
esac

echo "VALIDATION PASS ($slice)"
