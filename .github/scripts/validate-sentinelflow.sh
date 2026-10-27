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
      "/c/Users/$user_name/.local/bin/uv.exe"
      "/mnt/c/Users/$user_name/.local/bin/uv.exe"
      "/c/Users/$user_name/.local/bin/uv"
      "/mnt/c/Users/$user_name/.local/bin/uv"
      "/home/$user_name/.local/bin/uv"
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

resolve_pnpm_bin() {
  if command -v pnpm >/dev/null 2>&1 && pnpm --version >/dev/null 2>&1; then
    echo "pnpm"
    return 0
  fi
  echo "npx --yes pnpm"
}

PNPM_BIN="${PNPM_BIN:-$(resolve_pnpm_bin)}"

run_backend() {
  echo "[sentinelflow] backend: uv sync --extra dev && ruff check && ruff format --check && bandit && pip-audit && mypy && pytest && evals"
  (
    cd "$app_root/backend"
    "$UV_BIN" sync --extra dev
    "$UV_BIN" run --no-sync ruff check app
    "$UV_BIN" run --no-sync ruff format --check app
    "$UV_BIN" run --no-sync bandit -c pyproject.toml -x app/tests -r app -q
    "$UV_BIN" run --no-sync pip-audit --skip-editable
    "$UV_BIN" run --no-sync mypy app
    "$UV_BIN" run --no-sync pytest --cov=app --cov-report=term-missing --cov-fail-under=80
    "$UV_BIN" run --no-sync python -m app.evals.run
  )
}

run_frontend() {
  echo "[sentinelflow] frontend: pnpm install && check-rules && eslint && prettier && pnpm audit && pnpm test && pnpm build"
  (
    cd "$app_root/frontend"
    $PNPM_BIN install
    "$NODE_BIN" scripts/check-rules.js
    npx eslint .
    npx prettier --check .
    $PNPM_BIN audit --audit-level=high
    $PNPM_BIN test
    $PNPM_BIN build
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

run_security_check() {
  echo "[sentinelflow] security: running OWASP Top 10, LLM Top 10 & CWE/CVE compliance suite"
  (
    cd "$app_root/backend"
    "$UV_BIN" run --no-sync python ../ops/security_compliance_scan.py
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
  security)
    run_security_check
    ;;
  all|cross-stack|crossstack)
    run_security_check
    run_backend
    run_contract_check
    run_frontend
    ;;
  *)
    echo "Usage: $0 [backend|frontend|contract|security|all]" >&2
    exit 2
    ;;
esac

echo "VALIDATION PASS ($slice)"
