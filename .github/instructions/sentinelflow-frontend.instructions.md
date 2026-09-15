---
name: SentinelFlow Frontend Rules
description: "Use when editing Next.js, React, TypeScript, CSS, API client, SSE, or console UI code in SentinelFlow frontend files."
applyTo: "sentinelflow/frontend/**/*.ts,sentinelflow/frontend/**/*.tsx,sentinelflow/frontend/**/*.css"
---
# SentinelFlow Frontend Rules

## Layer Ownership

- Fetch helpers and stream URL builders belong in `frontend/lib/api.ts`.
- EventSource lifecycle and event dispatch belong in `frontend/lib/sse.ts`.
- Long-lived client investigation state belongs in `frontend/hooks/useSentinelAgent.ts`.
- View components own presentation and local UI state only. Do not duplicate fetch or EventSource logic inside panels or pages.
- TypeScript types for API shapes and stream events belong in `frontend/lib/types.ts`.

## Before Editing

- Read `frontend/lib/types.ts` before touching any API-facing code to understand the current contract.
- If a backend response shape changed, update `types.ts` and every component that consumes the changed field in the same task.
- Use `startTransition` for state updates driven by SSE events, following the pattern in `useSentinelAgent.ts`.

## You Are NOT Done Until

- `bash .github/scripts/validate-sentinelflow.sh frontend` exits 0.
- If there is no automated test for the touched slice, state this explicitly — do not claim test coverage that does not exist.

A TypeScript error in the build is a broken change, regardless of whether the runtime behavior appears correct.