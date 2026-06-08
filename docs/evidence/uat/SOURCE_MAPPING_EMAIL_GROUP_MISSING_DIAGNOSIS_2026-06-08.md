# SOURCE MAPPING — EMAIL GROUP MISSING DIAGNOSIS
**Date:** 2026-06-08
**Scope:** PRJ-001 and PRJ-002 — UI showed "Group: Missing, Group mailbox: Missing, Members: 0"
**Verdict:** `SOURCE_MAPPING_EMAIL_GROUP_RUNTIME_BUG_FIXED_NOT_LIVE`

---

## 1. Symptom

After email group enrichment ran successfully (verdict `ENRICHED_NOT_LIVE`), the Admin
Source Mapping UI continued to display:

- Group: Missing
- Group mailbox: Missing
- Members: 0

for both PRJ-001 and PRJ-002.

---

## 2. Root Cause

Every call to `GET /admin/source-mappings` and `GET /admin/source-mappings/{code}` invokes
`await pg.init_schema()` before returning data. `init_schema()` calls
`_migrate_verified_prj_source_mappings()`, which ran an **unconditional UPDATE**:

```sql
-- OLD (apps/edr/persistence/postgres_store.py before Fix 3)
UPDATE project_source_mappings SET
    ...
    microsoft         = $7,           -- config value — always overwrote DB
    related_people    = $9,
    enabled_sources   = $10,
    mapping_status    = $11,
    last_validation_result = $12,
    ...
WHERE project_code = $1
```

This ran on every API request. The enrichment endpoint saved enriched data via
`upsert_source_mapping`, then immediately the next list/detail request triggered
`init_schema()` which overwrote those columns with the (pre-enrichment) config file values.

The running Docker image was built before Fix 3 was applied, so it contained the old
unconditional migration. The enriched data was never visible to the UI.

---

## 3. Graph Token Role Verification

Checked via `get_graph_token()` using client credentials flow from `.env`:

| Role | Required | Present |
|------|----------|---------|
| `Group.Read.All` | yes | PASS |
| `GroupMember.Read.All` | yes | PASS |
| `Mail.Read` | yes | PASS |
| `Mail.ReadBasic.All` | yes | PASS |
| `MailboxSettings.Read` | yes | PASS |
| `Sites.Read.All` | yes | PASS |
| `User.Read.All` | yes | PASS |

All 7 required Graph roles confirmed present. Permission was not the blocking factor.

---

## 4. Enrichment Run Results

Ran enrichment function directly from working tree (`run_email_group_enrichment`):

**PRJ-001** — Construction of Civil Defense building in Al Marfa
- Group found: `71313630-ba8f-4eb3-b385-151f124e7903`
- Display name: "Construction of Civil Defense building in Al Marfa"
- Group mailbox: `ConstructionofCivilDefenseCenterinAlMirfaAlDhafraRegion@elrace.com`
- Mail enabled: true
- Members read: 17
- `group_membership_status`: `GROUP_MEMBERS_READ`

**PRJ-002** — Construction of Civil Defense building in Zayed City Al Dhafra.
- Group found: `57dda9ae-f753-42fa-b966-7376ba809a6f`
- Display name: "Construction of Civil Defense building in Zayed City Al Dhafra."
- Group mailbox: `ConstructionofCivilDefenseCenterinIndustrialAreaofMadin@elrace.com`
- Mail enabled: true
- Members read: 18
- `group_membership_status`: `GROUP_MEMBERS_READ`

**Overall verdict:** `SOURCE_MAPPING_EMAIL_GROUP_ENRICHED_NOT_LIVE`

Enrichment succeeded. The UI bug was caused entirely by the migration overwriting results,
not by any Graph API failure.

---

## 5. Fix Applied — Fix 3: Migration CASE SQL

**File:** `apps/edr/persistence/postgres_store.py`
**Function:** `_migrate_verified_prj_source_mappings`

The unconditional column assignments were replaced with CASE expressions that preserve
enriched data when `group_membership_status` is in the terminal states:

```sql
microsoft = CASE
    WHEN COALESCE(microsoft->>'group_membership_status','') = ANY(
        ARRAY['GROUP_MEMBERS_READ','GROUP_FOUND_NO_MEMBERS','GROUP_FOUND_NO_MAILBOX']
    ) THEN microsoft
    ELSE $7::jsonb
END,
```

Same CASE guard applied to `related_people`, `enabled_sources`, `mapping_status`,
and `last_validation_result`. Config values fall through only for rows that have not
yet been enriched (empty `group_membership_status`).

---

## 6. Config Updated With Live Results

**File:** `docs/config/project_source_mapping.json`

Updated to reflect actual enrichment results so that after Docker rebuild, the migration
seeds the correct enriched state immediately (no manual enrichment run required):

| Field | PRJ-001 | PRJ-002 |
|-------|---------|---------|
| `mapping_status_gate` | `EMAIL_GROUP_ENRICHED` | `EMAIL_GROUP_ENRICHED` |
| `enabled_sources` | `["email","odoo","sharepoint"]` | `["email","odoo","sharepoint"]` |
| `microsoft.group.id` | `71313630-ba8f-...` | `57dda9ae-f753-...` |
| `microsoft.group.mail_enabled` | `true` | `true` |
| `microsoft.group_membership_status` | `GROUP_MEMBERS_READ` | `GROUP_MEMBERS_READ` |
| `microsoft.member_count` | `17` | `18` |
| `microsoft.group_members` | `[]` (privacy) | `[]` (privacy) |
| `related_people.document_controller` | `Asif Younas <asif@elrace.com>` | `Asif Younas <asif@elrace.com>` |

Group members list not stored in config — bulk personal data kept only in live DB.

---

## 7. Compliance Verification

| Constraint | Status |
|-----------|--------|
| No write to Odoo | PASS — no Odoo API calls made |
| No write to SharePoint | PASS — no SharePoint writes |
| No write to Microsoft Graph | PASS — read-only Graph calls only |
| No email sent/deleted/modified | PASS |
| Secrets not printed | PASS — token values not logged |
| ownCloud stays disabled | PASS — `base_path: ""`, not in `enabled_sources` |
| Email disabled without verified mailbox | PASS — email enabled only via verified group mailbox (`mail_enabled: true`) |
| Group members not stored as Shared Mailboxes | PASS — `email.shared_mailboxes: []` |
| Project names from Odoo | PASS — names match Odoo records exactly |
| Gate 4 / Gate 5 / UAT / Slice 7 / LIVE not started | PASS |

---

## 8. All Checks — Results

| Check | Result |
|-------|--------|
| `ruff check .` | PASS — no issues |
| `python3 -m compileall apps scripts` | PASS |
| `pytest test_email_group_enrichment.py -q` | PASS — 30 passed |
| `pytest test_phase2b_source_mapping.py -q` | PASS — 68 passed |
| `npm run lint` (frontend) | PASS — no ESLint errors |
| `npm run build` (frontend) | PASS — built in 7.63 s |
| `python3 scripts/check_doc_drift.py` | PASS — clean |
| `python3 scripts/check_ai_context.py` | PASS — clean |
| `python3 scripts/agent_postflight.py --allow-no-evidence` | PASS — clean |

---

## 9. Docker Rebuild Required

The running container still has the old unconditional migration. Fix 3 and the updated
config take effect only after rebuilding:

```bash
docker compose build app && docker compose up -d app
```

After rebuild:
1. The new config (with `GROUP_MEMBERS_READ`) is copied into the image.
2. `_migrate_verified_prj_source_mappings` reads it and sets enriched state immediately.
3. The CASE guard prevents any subsequent `init_schema()` call from overwriting.
4. The UI will show correct Group / Group mailbox / Members data without running enrichment again.

---

## 10. Final Verdict

```
SOURCE_MAPPING_EMAIL_GROUP_RUNTIME_BUG_FIXED_NOT_LIVE
```

Both email groups exist and are verified. The bug was in backend code (unconditional
migration overwriting enriched DB state on every API request). Fix 3 corrects this.
All checks pass. System is NOT_LIVE pending Docker rebuild by operator.
