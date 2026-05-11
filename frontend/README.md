# DecisionCenter Frontend

Phase 1I frontend foundation. **Bootstrap slice only** — this directory currently
contains just the Vite + React + TypeScript + Tailwind toolchain with a
placeholder app. There is intentionally no router, no design-token layer, no
reusable components, no API client, and no auth code yet; those arrive in later
Phase 1I slices.

See [`../docs/design/PHASE_1I_UI_CONTRACT.md`](../docs/design/PHASE_1I_UI_CONTRACT.md)
and [`../docs/execution/PHASE_1I_PLAN.md`](../docs/execution/PHASE_1I_PLAN.md).

## Requirements

- Node.js 20.19+ or 22.12+ (Vite 6).

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Start the Vite dev server. |
| `npm run build` | Type-check (`tsc -b`) and produce a production build. |
| `npm run preview` | Preview the production build locally. |
| `npm run lint` | Run ESLint. |
| `npm run format` | Format with Prettier. |
| `npm run format:check` | Check formatting without writing. |

## Scope guardrails (Phase 1I)

- No `fetch`, `axios`, `XMLHttpRequest`, websocket, event stream, or other
  network/data-fetching layer.
- No environment-driven API base URL, no auth/token handling.
- No backend, CI, deployment, or agent-state changes from this directory.
