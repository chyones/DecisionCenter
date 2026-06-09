# DASHBOARD STATUS WORDING FIX
**Date:** 2026-06-08
**Scope:** Replace misleading "connectors pending" banner with accurate wording

---

## 1. Problem

The dashboard and Connectors page both displayed:

```
Partial — core up, connectors pending
core platform, edge and login are up; pending live validation: anthropic, voyage, cohere
Blocking go-live: anthropic, voyage, cohere
```

The phrase **"connectors pending"** implies Microsoft connectors (SharePoint, Graph,
Odoo, Entra) are still unverified. They are not. The only remaining blockers are
AI provider keys (Anthropic, Voyage, Cohere), which are intentionally unconfigured.

---

## 2. Actual Connector States (at time of fix)

| Connector | State | Satisfies go-live |
|-----------|-------|-------------------|
| Entra Auth | `VALIDATED` | Yes |
| Odoo | `LIVE_OK` | Yes |
| SharePoint | `VERIFIED_FROM_EVIDENCE` | Yes |
| Email / Graph | `VERIFIED_FROM_EVIDENCE` | Yes |
| n8n | `LIVE_OK` | Yes |
| ownCloud | `DISABLED` (intentional) | N/A — not required |
| Anthropic | `NOT_CONFIGURED` | **No** |
| Voyage | `NOT_CONFIGURED` | **No** |
| Cohere | `NOT_CONFIGURED` | **No** |

---

## 3. Changes Made

### Backend — `apps/edr/admin/connector_status.py`

Added contextual branch to `_compute_readiness`. When the only remaining
blockers are AI providers, the reason string explicitly names them:

```python
ai_blockers = [n for n in not_live if by_name.get(n) and by_name[n].group == "ai_provider"]
if len(ai_blockers) == len(not_live):
    ai_display = [by_name[n].display_name for n in ai_blockers]
    return (
        "PARTIAL_READY",
        "Core platform, edge, login, Odoo, SharePoint, Graph, and Email are "
        "validated or verified. AI report generation is blocked until "
        + ", ".join(ai_display) + " keys are configured.",
    )
```

The generic fallback for other PARTIAL_READY cases is unchanged.

### Frontend — `frontend/src/screens/ConnectorTruthPanel.tsx`

**`readinessTitle(report)`** — dynamic banner title:
```tsx
function readinessTitle(report: ConnectorTruthReport): string {
  if (report.readiness !== 'PARTIAL_READY') return READINESS_LABEL[report.readiness];
  const aiNames = new Set(report.ai_providers.map((t) => t.name));
  if (report.blocking.length > 0 && report.blocking.every((n) => aiNames.has(n))) {
    return 'Microsoft connectors ready — AI providers pending';
  }
  return READINESS_LABEL['PARTIAL_READY'];
}
```

**`blockingLine(report)`** — formatted blocking footer:
```tsx
function blockingLine(report: ConnectorTruthReport): string {
  const aiNames = new Set(report.ai_providers.map((t) => t.name));
  const allAI = report.blocking.every((n) => aiNames.has(n));
  if (allAI && report.blocking.length > 0) {
    const displayNames = report.blocking
      .map((n) => report.ai_providers.find((t) => t.name === n)?.display_name ?? n)
      .join(', ');
    return `AI providers missing: ${displayNames}`;
  }
  return `Blocking go-live: ${report.blocking.join(', ')}`;
}
```

---

## 4. New UI Wording (after rebuild)

| Field | Before | After |
|-------|--------|-------|
| Main status | `Partial — core up, connectors pending` | `Microsoft connectors ready — AI providers pending` |
| Summary | `core platform, edge and login are up; pending live validation: anthropic, voyage, cohere` | `Core platform, edge, login, Odoo, SharePoint, Graph, and Email are validated or verified. AI report generation is blocked until Anthropic (report generation), Voyage (embeddings), Cohere (rerank) keys are configured.` |
| Blocking line | `Blocking go-live: anthropic, voyage, cohere` | `AI providers missing: Anthropic (report generation), Voyage (embeddings), Cohere (rerank)` |
| ownCloud | `Disabled` | `Disabled` (unchanged — intentional, not a blocker) |

The `PARTIAL_READY` colour class (amber/warning) is unchanged — the readiness
state itself hasn't changed, only the wording is more precise.

---

## 5. Tests Added — `test_connector_truth.py`

| Test | What it proves |
|------|---------------|
| `test_satisfies_go_live_for_validated_and_verified_states` | VALIDATED / LIVE_OK / VERIFIED_FROM_EVIDENCE each return `_satisfies_go_live=True`; CONFIGURED_NOT_TESTED / NOT_CONFIGURED / DISABLED do not |
| `test_partial_ready_reason_names_ai_providers_when_microsoft_verified` | When Entra=VALIDATED, Odoo=LIVE_OK, SharePoint/Graph=VERIFIED_FROM_EVIDENCE, `_compute_readiness` reason names Anthropic/Voyage/Cohere — not Microsoft connectors |
| `test_ai_provider_blocking_does_not_put_microsoft_connectors_in_blocking_list` | Blocking list is exactly `{anthropic, voyage, cohere}` — no Microsoft connector names appear |
| `test_all_microsoft_connectors_verified_gives_ready_for_uat_when_ai_configured` | When all connectors satisfy go-live, readiness is `READY_FOR_UAT` and blocking list is empty |

---

## 6. All Checks

| Check | Result |
|-------|--------|
| `ruff check .` | PASS |
| `python3 -m compileall apps scripts` | PASS |
| `pytest test_connector_truth.py -q` | PASS — 37 passed |
| `npm run lint` | PASS |
| `npm run build` | PASS — built in 6.59 s |
| `check_doc_drift.py` | PASS — clean |
| `check_ai_context.py` | PASS — clean |
| `agent_postflight.py` | PASS — clean |

---

## 7. Compliance

| Constraint | Status |
|-----------|--------|
| AI providers not configured | PASS — no keys added |
| ownCloud stays disabled | PASS — unchanged |
| No Gate 4 / Gate 5 / UAT / LIVE started | PASS |
| Backend connector logic unchanged | PASS — only `_compute_readiness` wording branch added |
| Production remains NOT_LIVE | PASS |

---

## 8. Final Verdict

```
DASHBOARD_STATUS_WORDING_FIXED_NOT_LIVE
```
