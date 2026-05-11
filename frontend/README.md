# DecisionCenter Frontend

Phase 1I frontend foundation, being built in locked slices. **Implemented so
far:** the Vite + React + TypeScript + Tailwind toolchain (Slice 1) and the
design-token + status registry layer (Slice 2). There is intentionally **no**
router, **no** reusable components, **no** layout shell, **no** role guards, and
**no** API client yet; those arrive in later Phase 1I slices.

See [`../docs/design/PHASE_1I_UI_CONTRACT.md`](../docs/design/PHASE_1I_UI_CONTRACT.md)
and [`../docs/execution/PHASE_1I_PLAN.md`](../docs/execution/PHASE_1I_PLAN.md).

## Requirements

- Node.js 20.19+ or 22.12+ (Vite 6).

## Layout

| Path | Contents |
|---|---|
| `src/tokens/` | Design tokens — colors, typography, spacing, radius, shadows, fixed layout dimensions — plus the 13-value status registry and the named screen-level states. Mirrors `PHASE_1I_UI_CONTRACT.md` §A–§C. |
| `src/tokens/contract-assertions.ts` | Compile-time (`tsc`) checks that the token layer matches the contract. No test runner is wired yet. |
| `src/index.css` | Tailwind import + `@theme` block carrying the same tokens as CSS variables, plus the dark-theme base. |
| `src/App.tsx`, `src/main.tsx` | Placeholder app entry (no application code). |

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
