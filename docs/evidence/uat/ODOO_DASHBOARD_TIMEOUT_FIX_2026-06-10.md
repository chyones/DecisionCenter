# Odoo Dashboard Timeout Reliability Fix — 2026-06-10

## Status

**IMPLEMENTED_CI_GREEN_NOT_LIVE**

Production remains `NOT_LIVE`. This change did not deploy the app, import the
n8n workflow, restart services, or change credentials.

## Reported Symptom

The admin connector card reported:

- Odoo: `Unreachable`
- Evidence: `Odoo webhook unreachable: TimeoutError`
- Last verified: 2026-06-10 11:13:09

## Redacted Diagnosis

- App-to-n8n TCP connectivity succeeded in 0.013 seconds.
- Required Odoo, n8n, and webhook-auth settings were present; values were not
  printed.
- Three immediate read-only Odoo probes succeeded in 4.392, 4.858, and 4.922
  seconds.
- The dashboard requested 5 records, but the deployed workflow returned 100
  because `n8n/odoo_read.json` hard-coded `limit:100`.
- The dashboard probe used a fixed 10-second timeout while ordinary connector
  calls use configurable `N8N_TIMEOUT` (60 seconds in this environment).
- Under concurrent test/evaluation load, a read-only probe reached the
  configured 60-second timeout. After load ended, the currently deployed
  10-second probe succeeded in 4.604 seconds with live Odoo evidence.

The evidence shows an intermittent latency problem, not a persistent
app-to-n8n network failure. Returning 100 records for a five-record health
probe unnecessarily increased latency and made the fixed timeout fragile.

## Changes

- `apps/edr/admin/connector_status.py`
  - Odoo truth probes now use the greater of 10 seconds or configured
    `N8N_TIMEOUT`.
- `n8n/odoo_read.json`
  - Validates an optional request limit as an integer from 1–100.
  - Passes that bounded limit to Odoo `search_read`.
  - Keeps the existing default of 100 for callers that omit the limit.
- Added focused tests for the five-record dashboard request, timeout selection,
  and bounded n8n workflow limit.
- Updated the locked workflow specification and connector operations guide.

## Validation

| Check | Result |
|---|---|
| Focused connector truth + security tests | 63 passed |
| CI-equivalent integration tests | 720 passed, 1 skipped, 14 live probes deselected |
| Smoke tests | 2 passed |
| Phase 2A local E2E validator | PASS, 18 workflow nodes visited |
| Golden-set evaluation | 64/64 passed; 100% pass rate; 93.75% precision |
| Playwright UI | 78 passed across Chromium, Firefox, and WebKit |
| Ruff | clean |
| Python compileall | clean |
| Frontend lint | clean |
| Frontend build | passed with existing Vite large-chunk warning |
| n8n workflow JSON | valid JSON |
| n8n Code-node script | syntax-valid when checked in its async execution wrapper |
| Documentation drift | clean before governance refresh |
| AI context | clean before governance refresh |
| GitHub Actions | run `27261573729`: frontend success; smoke success |

The host Python installation has an unrelated FastAPI/Pydantic mismatch, so
authoritative pytest runs used the repository's pinned app image with the
current worktree bind-mounted.

## Runtime Boundary

The source fix is not active in the deployed app or active n8n workflow until
an explicitly approved rollout. The existing deployed workflow still returns
100 records. No rollout was performed in this task.
