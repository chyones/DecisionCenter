# ENTRA CONNECTOR DISPLAY WORDING FIX
**Date:** 2026-06-08
**Scope:** Frontend-only display fix for Microsoft Entra Auth connector row

---

## 1. Problem

The Connectors & APIs page showed the Entra Auth connector as:

```
Last verified: <timestamp>  data: evidence · 1 records
```

This wording is misleading in two ways:

1. **"data: evidence"** implies the connector returned business data with source
   "evidence". Entra Auth does not return business data. It returns a validation
   proof that an OIDC/JWKS check succeeded and a signed validation marker was
   accepted. The word "data" is incorrect in this context.

2. **"1 records"** — grammatically wrong, and semantically wrong. `sample_count=1`
   for Entra means "one validation token was checked", not one business record.

---

## 2. Root Cause

`ConnectorRow` in `ConnectorTruthPanel.tsx` used a single generic template for
all connectors:

```tsx
{t.data_source !== 'none' && (
  <span className="ml-2 rounded-sm border border-border px-1">
    data: {t.data_source}
  </span>
)}
{t.sample_count != null && (
  <span className="ml-2">· {t.sample_count} records</span>
)}
```

For `entra_auth` with `data_source="evidence"` and `sample_count=1`, this
produced the misleading output above.

---

## 3. Fix — Frontend only

Added a `dataSourceChip(t: ConnectorTruth)` helper function in
`frontend/src/screens/ConnectorTruthPanel.tsx` that handles the Entra special
case before the generic path:

```tsx
function dataSourceChip(t: ConnectorTruth): React.ReactNode {
  if (t.data_source === 'none') return null;
  if (t.name === 'entra_auth' && t.data_source === 'evidence') {
    return (
      <span className="ml-2 rounded-sm border border-border px-1">
        validation evidence · validated once
      </span>
    );
  }
  return (
    <>
      <span className="ml-2 rounded-sm border border-border px-1">
        data: {t.data_source}
      </span>
      {t.sample_count != null && (
        <span className="ml-2">· {t.sample_count} records</span>
      )}
    </>
  );
}
```

`ConnectorRow`'s `Last verified` line now calls `{dataSourceChip(t)}`.

**Before:**
```
Last verified: 6/8/2026, 10:00:00 AM  data: evidence · 1 records
```

**After:**
```
Last verified: 6/8/2026, 10:00:00 AM  validation evidence · validated once
```

---

## 4. Scope Boundaries

| What changed | What did NOT change |
|---|---|
| `ConnectorTruthPanel.tsx` — display label for `entra_auth` | Connector truth logic (`connector_status.py`) |
| Chip content for Entra auth only | Entra validation logic (`_probe_entra`, `_entra_validation_marker`) |
| Pluralization fix scoped to Entra row | All other connector rows |
| | Backend API response |
| | `data_source` field values |
| | `sample_count` values |
| | Any go-live gate |

---

## 5. All Checks

| Check | Result |
|-------|--------|
| `ruff check .` | PASS |
| `python3 -m compileall apps scripts` | PASS |
| `npm run lint` | PASS |
| `npm run build` | PASS — built in 5.62 s |
| `check_doc_drift.py` | PASS — clean |
| `check_ai_context.py` | PASS — clean |
| `agent_postflight.py` | PASS — clean |

---

## 6. Compliance

| Constraint | Status |
|-----------|--------|
| Connector truth logic unchanged | PASS |
| Entra validation logic unchanged | PASS |
| No Gate 4 / Gate 5 / UAT / LIVE started | PASS |
| No secrets printed | PASS |
| Production remains NOT_LIVE | PASS |

---

## 7. Final Verdict

```
ENTRA_CONNECTOR_DISPLAY_WORDING_FIXED_NOT_LIVE
```
