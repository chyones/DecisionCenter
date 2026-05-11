# Agent Handoff — DecisionCenter

## What Was Done

Phase 1H (Evaluation & Hardening) is complete. A lightweight AI agent operating
layer was added afterward (`AGENTS.md`, `docs/ai/skills/README.md`,
`docs/ai/failure-modes.md`, `docs/ai/task-template.md`,
`scripts/agent_preflight.py`, `scripts/agent_postflight.py`).

### Phase 1H — Evaluation & Hardening

- `apps/edr/evaluation/run.py` — real evaluation runner: JSONL loader, single-node
  and full-workflow case execution, dot-notation expectation resolution, aggregate
  metrics (pass rate, precision, refusal accuracy), CLI flags
  (`--suite`, `--min-pass-rate`, `--min-precision`, `--max-failures`), non-zero
  exit on regression.
- `apps/edr/evaluation/goldenset/goldenset.jsonl` — 65 executable cases across all
  12 baseline categories; stale `example.jsonl` deleted.
- `apps/edr/graph/node_13_quality_gate.py` — strict claim-to-evidence binding;
  financial snapshot fields require an Odoo `evidence_id` when marked available.
- `apps/edr/evaluation/promptfoo.config.yaml` — structured placeholder (providers
  and category mapping defined; `tests` empty until promptfoo CLI is available;
  CI does not gate on promptfoo).
- `apps/edr/exporters/pdf.py` — bundled `Amiri-Regular.ttf` (OFL), Arabic
  auto-detection, RTL limitation disclaimer. Known limitation: no bidi shaping or
  Arabic reshaping yet.
- `apps/edr/evaluation/load_test.py` — local-only deterministic load test,
  semaphore-bounded concurrency, latency percentiles; baseline-only, no permanent
  thresholds.
- `pyproject.toml` — pip-audit triage: `cryptography` 44.0.1, `python-dotenv`
  1.2.2, `PyJWT` 2.12.0. Remaining advisories accepted as deferred major-version
  bumps; `pip-audit` stays `continue-on-error: true`.
- `.github/workflows/ci.yml` — `Evaluation suite` step
  (`--min-pass-rate 0.95 --min-precision 0.90`), job-level `N8N_TIMEOUT: 5`,
  config-coverage assertion updated to 40 keys.
- Tests: `test_evaluation.py` (15), `test_load_test.py` (5), `test_pdf_arabic.py` (7).

### AI Operating Layer

- `AGENTS.md` — mandatory operating context: source-of-truth order, phase rules,
  verification rules, security/deployment rules, coordination rules.
- `docs/ai/skills/README.md` — task-classification table with per-skill required
  validation.
- `docs/ai/failure-modes.md` — eight named failure modes with prevention,
  detection, and required response.
- `docs/ai/task-template.md` — pre-work planning template.
- `scripts/agent_preflight.py` / `scripts/agent_postflight.py` — read-only git +
  agent-state + doc/AI-context checks (preflight) and changed-file / blocked-pattern
  checks (postflight).

## Current Branch And Commit

- Branch: `main`
- Current verified commit (anchor): `074d5245912f39f7c7032314b0931a9abc3a247e`
- Status: `PHASE_1H_COMPLETE_NOT_LIVE`
- Production status: `NOT_LIVE`
- Latest report: `docs/execution/PHASE_1H_REPORT.md`

## What Was NOT Done

- Phase 1I (Frontend Foundation) not started — requires explicit user approval.
- No frontend UI added.
- No full Arabic bidirectional shaping/reshaping in PDF export.
- No promptfoo CLI integration (config is placeholder only).
- No permanent load-test p95 thresholds (baseline-only).
- `pip-audit` not promoted to a hard CI gate (19 advisories remain on 9 packages).
- No production deployment performed; no secrets or `.env` files committed.

## Must Read Before Next Work

- `AGENTS.md`
- `docs/ai/SHARED_CONTEXT.md`
- `docs/ai/agent-state.json`
- `docs/execution/PHASE_1H_REPORT.md`
- `docs/execution/IMPLEMENTATION_PHASES.md`
- `docs/admin/CONTROL_PLANE_LOCK.md`

## Next Recommended Work

Phase 1I — Frontend Foundation & Static Admin Scaffolds — requires explicit user
approval. When authorized: initialize the `frontend/` project (Vite + React +
TypeScript + Tailwind), implement design tokens and the layout shell, build
reusable components and role-guarded routing, and add static admin scaffolds with
no API wiring, per `docs/design/UI_CONTRACT_v1.md`. Add `frontend/` lint and build
steps to CI.

## Validation Proof (Phase 1H closeout)

- `make smoke`: 2 passed.
- `make test`: 143 passed.
- `make eval`: 65/65 passed, 100.00% pass rate, 92.31% precision.
- `ruff check .`: clean.
- `python3 -m compileall apps scripts`: clean.
- `python3 scripts/check_doc_drift.py`: clean.
- `python3 scripts/check_ai_context.py`: clean.

## Final Status

`PHASE_1H_COMPLETE_NOT_LIVE`
