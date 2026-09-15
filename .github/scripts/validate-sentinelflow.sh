#!/usr/bin/env bash
set -euo pipefail

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

run_backend() {
  echo "[sentinelflow] backend: uv sync --extra dev && uv run ruff check app && uv run pytest"
  (
    cd "$app_root/backend"
    "$UV_BIN" sync --extra dev
    "$UV_BIN" run ruff check app
    "$UV_BIN" run pytest
  )
}

run_frontend() {
  echo "[sentinelflow] frontend: pnpm install && pnpm build"
  (
    cd "$app_root/frontend"
    pnpm install
    pnpm build
  )
}

case "$slice" in
  backend)
    run_backend
    ;;
  frontend)
    run_frontend
    ;;
  all|cross-stack|crossstack)
    run_backend
    run_frontend
    ;;
  *)
    echo "Usage: $0 [backend|frontend|all]" >&2
    exit 2
    ;;
esac

echo "VALIDATION PASS ($slice)"
