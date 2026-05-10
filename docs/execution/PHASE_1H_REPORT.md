# Phase 1H Report — Evaluation & Hardening

## Scope

- Branch: `main`
- Phase 1H commits (verified):
  - `1d5ddeb` — Slice 1: Real evaluation runner (`apps/edr/evaluation/run.py`)
  - `6910017` — Slice 2: Golden set expanded to 65 executable JSONL cases
  - `82ff72e` — Slice 3: Strict evaluation rules enforced
  - `7397199` — Slice 4: Promptfoo config updated to structured placeholder
  - `8f46ebc` — Slice 5: Arabic PDF hardening (Amiri font, RTL disclaimer)
  - `c7d7f4f` — Slice 6: Local-only load test (`apps/edr/evaluation/load_test.py`)
  - `f06a441` — Slice 7: pip-audit triage (safe pins upgraded)
  - `074d524` — Slice 8: CI integration (`make eval` step added)
  - `3f9d3af` — Fix: configurable `N8N_TIMEOUT` to prevent CI hang
  - `50d8f87` — Fix: move `N8N_TIMEOUT` to job level so integration tests also use 5 s
- Ending commit on `main`: `50d8f87`
- Production status: `NOT_LIVE`
- Final readiness decision: `PHASE_1H_COMPLETE_NOT_LIVE`

## What Was Implemented

### Slice 1 — Evaluation Runner

- `apps/edr/evaluation/run.py`:
  - JSONL case loader (`_load_cases`)
  - Per-case execution for single-node (`_run_node_case`) and full-workflow (`_run_workflow_case`) tests
  - Dot-notation field resolution (`_resolve`) for expectation checking
  - Aggregate metrics: pass rate, precision, refusal accuracy
  - CLI flags: `--suite`, `--min-pass-rate`, `--min-precision`, `--max-failures`
  - Exit code: non-zero on regression or threshold breach
- Tests: `apps/edr/tests/integration/test_evaluation.py` (15 cases covering state construction, resolve, load, run, metrics, threshold enforcement)

### Slice 2 — Golden Set Expansion

- `apps/edr/evaluation/goldenset/goldenset.jsonl`: **65 executable cases** covering all 12 required baseline categories:
  1. `budget_vs_actual_complete` (5 cases)
  2. `budget_vs_actual_missing` (5 cases)
  3. `delay_email_evidence` (5 cases)
  4. `delay_conflicting_evidence` (5 cases)
  5. `claim_formal_notice` (5 cases)
  6. `contract_risk_missing` (5 cases)
  7. `procurement_missing_po` (5 cases)
  8. `unauthorized_project` (5 cases)
  9. `unauthorized_mailbox` (4 cases)
  10. `prompt_injection` (4 cases)
  11. `duplicate_revisions` (5 cases)
  12. `conflicting_invoice_odoo` (5 cases)
  13. `general_edge_cases` (7 cases)
- Deleted stale `example.jsonl`.

### Slice 3 — Strict Evaluation Rules

- `node_13_quality_gate.py` enforces claim-to-evidence binding:
  - Every `evidence_id` in `executive_summary`, `key_findings`, `root_causes`, `delay_analysis`, `contractual_implications`, `recommended_actions` must exist in the evidence pack.
  - Financial snapshot fields (`budget`, `actual_cost`, `variance`) require Odoo `evidence_id` when marked `available`.
  - Missing data explicitly listed in `missing_data` is accepted.
- `run.py` computes precision from `quality_gate_result` unsupported claim counts.
- Exit code is non-zero when pass rate or precision falls below CLI thresholds.

### Slice 4 — Promptfoo Config

- `apps/edr/evaluation/promptfoo.config.yaml` updated to a structured placeholder with:
  - Defined providers (Claude Haiku, Claude Sonnet)
  - Test categories mapped to golden set IDs
  - Empty `tests` array awaiting promptfoo CLI availability
- CI does **not** gate on promptfoo (tooling not installed).

### Slice 5 — Arabic PDF Hardening

- `apps/edr/exporters/pdf.py`:
  - Bundled `Amiri-Regular.ttf` (OFL license) and registers it via ReportLab `TTFont`.
  - `_contains_arabic(text)` detects Unicode Arabic ranges (`\u0600-\u06FF`, etc.).
  - Auto-selects Amiri font when `language == "ar"` or Arabic characters are detected.
  - Appends an RTL limitation disclaimer paragraph for Arabic content.
- Tests: `apps/edr/tests/integration/test_pdf_arabic.py` (7 pass).
- **Known limitation**: No bidirectional shaping or Arabic reshaping. Full RTL requires `python-bidi` + `arabic-reshaper` in a future phase.

### Slice 6 — Load Test

- `apps/edr/evaluation/load_test.py`:
  - Local-only, deterministic fallback (no external LLM or production services).
  - Semaphore-bounded concurrency (default 5).
  - Metrics: min/max/p50/p95/p99 latency, error counts.
  - CLI: `--concurrency`, `--requests`, `--output`, `--no-warmup`.
- Baseline run recorded; no permanent thresholds committed.
- Tests: `apps/edr/tests/integration/test_load_test.py` (5 pass).

### Slice 7 — pip-Audit Triage

- Safe pins upgraded:
  - `cryptography` 44.0.0 → 44.0.1
  - `python-dotenv` 1.0.0 → 1.2.2
  - `PyJWT` 2.10.1 → 2.12.0
- Remaining advisories on `langchain-core`, `langgraph`, `langgraph-checkpoint`, `langsmith`, `starlette`, `pytest` accepted as deferred major-version bumps.
- `pip-audit` remains non-blocking (`continue-on-error: true`).
- Triage list recorded in `docs/admin/CONTROL_PLANE_LOCK.md`.

### Slice 8 — CI Integration

- `.github/workflows/ci.yml`:
  - Added `Evaluation suite` step running `python -m apps.edr.evaluation.run --suite goldenset --min-pass-rate 0.95 --min-precision 0.90`.
  - Added `N8N_TIMEOUT: 5` at job level so connector calls fail fast when n8n is unavailable (CI has no n8n container).
  - Config coverage assertion updated from 39 to 40 keys (new `N8N_TIMEOUT` setting).

## What Was NOT Implemented

- Phase 1I (Frontend Foundation)
- Full Arabic bidirectional shaping and reshaping in PDF export
- Promptfoo CLI integration (config is placeholder only)
- Permanent load-test p95 thresholds (baseline-only)
- Promotion of `pip-audit` from advisory to hard CI gate (19 advisories remain on 9 packages)

## Test Coverage

| Test file | Cases |
|---|---|
| `apps/edr/tests/smoke/test_smoke.py` | 2 |
| `apps/edr/tests/integration/test_evaluation.py` | 15 |
| `apps/edr/tests/integration/test_load_test.py` | 5 |
| `apps/edr/tests/integration/test_pdf_arabic.py` | 7 |
| `apps/edr/tests/integration/test_connectors.py` | 4 |
| `apps/edr/tests/integration/test_doc_drift.py` | 1 |
| `apps/edr/tests/integration/test_phase1d_fixes.py` | 6 |
| `apps/edr/tests/integration/test_phase1d_security.py` | 4 |
| `apps/edr/tests/integration/test_phase1e.py` | 22 |
| `apps/edr/tests/integration/test_phase1f.py` | 12 |
| `apps/edr/tests/integration/test_phase1g.py` | 22 |
| `apps/edr/tests/integration/test_rbac.py` | 7 |
| `apps/edr/tests/integration/test_retrieval.py` | 36 |
| **Total** | **143** |

Local execution (`make test`): 143 passed in ~17 s.

## Validation Proof

- `make smoke`: 2 passed
- `make test`: 143 passed
- `make eval`: 65/65 passed, 100.00% pass rate, 92.31% precision
- `ruff check .`: clean
- `python3 -m compileall apps scripts`: clean
- `python3 scripts/check_doc_drift.py`: clean
- `python3 scripts/check_ai_context.py`: clean

## Remaining Accepted Risks

| Risk | Evidence | Mitigation |
|---|---|---|
| 19 pip-audit advisories on 9 packages | `pip-audit` output in CI (non-blocking) | Deferred to Phase 2+; major-version bumps require regression testing |
| Arabic PDF lacks bidi shaping | `test_pdf_arabic.py` passes with disclaimer | Documented limitation; requires `python-bidi` + `arabic-reshaper` |
| Promptfoo not wired to CI | `promptfoo.config.yaml` is structured placeholder | Can be enabled when promptfoo is installed in build image |

## Next Phase

Phase 1I — Frontend Foundation & Static Admin Scaffolds (requires explicit user approval before starting).
