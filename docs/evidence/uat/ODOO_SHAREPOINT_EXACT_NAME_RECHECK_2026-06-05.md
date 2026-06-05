# Odoo ↔ SharePoint Exact-Name Matching Recheck

> **Final verdict:** `ODOO_SHAREPOINT_EXACT_MATCH_BLOCKED_NOT_LIVE`
> **Date:** 2026-06-05
> **Timestamp (UTC):** 2026-06-05T07:05:56Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** `main` tracking `origin/main`
> **Production status:** NOT_LIVE
> **Gate 4:** Blocked (not started)
> **Gate 5:** Not started
> **Slice 6 UAT:** Not started
> **Slice 7:** Not started

---

## 1. Git State

| Item | Value |
|------|-------|
| `git rev-parse HEAD` | `fc54c64cd37adb234c01296bf34dd89274196602` |
| `git status --short --branch` | `main...origin/main` with unstaged connector/node/frontend changes and untracked evidence files |

---

## 2. Objective

Re-run the strict normalized exact-name matching dry-run **after** the operator claimed project names were aligned between Odoo and SharePoint.

**Target projects:**
- **PRJ-001 (Al Mirfa)** — `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type “D”. CD Al Mirfa – D`
- **PRJ-002 (Madinat Zayed)** — `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”. CD Madinat Zayed – D`

**Method:** Read-only scan of **all active Odoo projects** (up to 1,000) against the SharePoint `displayName` and `name` values, using deterministic normalization. No writes to any system.

---

## 3. SharePoint Projects Inspected

Read-only Graph calls:

```text
GET /sites/{site_id}?$select=id,displayName,name,webUrl,createdDateTime
GET /drives/{drive_id}/root/children?$top=1
```

| Project code | Site `name` | `displayName` | `webUrl` | Created | Drive children |
|--------------|-------------|---------------|----------|---------|----------------|
| PRJ-001 | `CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type “D”. CD Al Mirfa – D` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | 2025-12-15 | present |
| PRJ-002 | `CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”. CD Madinat Zayed – D` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed` | 2025-12-15 | present |

Both sites are live and readable.

---

## 4. Odoo Candidates Inspected

### 4.1 Scan scope

- **Model:** `project.project`
- **Domain:** `[('active', '=', True)]`
- **Limit:** 1,000 records
- **Actual records scanned:** 1,000 active projects
- **Fields read:** `id`, `name`, `display_name`, `active`, `user_id`, `partner_id`, `message_partner_ids`, `message_follower_ids`, `create_date`, `write_date`, `project_code`, `analytic_account_id`

### 4.2 Normalization method (deterministic)

1. Lowercase.
2. Replace curly quotes with straight quotes.
3. Replace en-dash / em-dash with a single space.
4. Remove all remaining punctuation (replace with space).
5. Collapse any whitespace sequence to a single space.
6. Trim leading and trailing spaces.

No stopwords removed. No stemming.

### 4.3 Exact match results

| Project code | SharePoint normalized target | Odoo exact matches | Classification |
|--------------|------------------------------|--------------------|----------------|
| PRJ-001 | `construction of civil defense center in al mirfa al dhafra region type d cd al mirfa d` | **0** | **NO_EXACT_MATCH** |
| PRJ-002 | `construction of civil defense center in industrial area of madinat zayed al dhafra region type d cd madinat zayed d` | **0** | **NO_EXACT_MATCH** |

**Additional checks:**
- Exact raw `name` equality in Odoo: **0 matches** for both targets.
- Exact raw `display_name` equality in Odoo: **0 matches** for both targets.
- Exact match against SharePoint site `name` (URL slug): **0 matches** in Odoo.

### 4.4 Top Odoo candidates by sequence similarity

**PRJ-001 (Al Mirfa) — closest candidates:**

| Odoo ID | Odoo `display_name` | Seq sim % | Token overlap % | `project_code` | Customer | Assigned user | Followers |
|---------|---------------------|-----------|-----------------|----------------|----------|---------------|-----------|
| 14602 | `Construction of Civil Defense building in Al Marfa` | 61.76 % | 40.0 % | `209-2025` | Abu Dhabi Police | Ahmad Ezzat Anwar | 2 |
| 14601 | `Construction of Civil Defense building in Zayed City Al Dhafra.` | 64.86 % | 43.75 % | `208/2025` | Abu Dhabi Police | Ahmad Ezzat Anwar | 2 |
| 12895 | `Lighting Protection System - In Book at Al Dhafra Dental` | 44.29 % | 15.79 % | `AHS/C/20/2016` | Rafed Healthcare Supplies LLC | Mohamed Ahmed Soliman | 1 |

**PRJ-002 (Madinat Zayed) — closest candidates:**

| Odoo ID | Odoo `display_name` | Seq sim % | Token overlap % | `project_code` | Customer | Assigned user | Followers |
|---------|---------------------|-----------|-----------------|----------------|----------|---------------|-----------|
| 14601 | `Construction of Civil Defense building in Zayed City Al Dhafra.` | 58.76 % | 44.44 % | `208/2025` | Abu Dhabi Police | Ahmad Ezzat Anwar | 2 |
| 14602 | `Construction of Civil Defense building in Al Marfa` | 50.91 % | 33.33 % | `209-2025` | Abu Dhabi Police | Ahmad Ezzat Anwar | 2 |
| 14230 | `Full Maintenance for OPD at Ground Floor Madinat Zayed Hospital Al Dhafra` | 40.43 % | 16.67 % | `RAFED/SS/FM/00182` | Rafed Healthcare Supplies LLC | Ahmad Ezzat Anwar | 1 |

**Observation:** The best candidate for both targets is the **same Odoo project (14601)**, which is about **Zayed City / Al Dhafra** — not Al Mirfa or Madinat Zayed Industrial Area. This demonstrates that **token overlap and sequence similarity are not sufficient** to uniquely and correctly link the two systems.

---

## 5. Follower Pull Result

**No exact unique matches were found**, so follower data for the target projects was **not pulled**.

Follower-pull capability itself works (confirmed in prior evidence), but it cannot be exercised against an unidentified target project.

---

## 6. Can Mapping Be Updated Safely?

**No — not automatically.**

Because there are **zero exact normalized matches**, any automatic update of `project_source_mapping.json` would require:
- Fuzzy or token-based guessing, which is **explicitly prohibited** by the hard restrictions.
- Manual selection of the correct Odoo project by a human operator.

The mapping config already contains `display_name` and `sharepoint_aliases` (added by the operator in `PROJECT_DISPLAY_NAMES_FIXED_FROM_SHAREPOINT_2026-06-05.md`), but these are **config-level UI labels**, not evidence of Odoo-to-SharePoint name alignment.

---

## 7. Why the Operator’s Alignment Claim Did Not Produce an Exact Match

The operator’s evidence file (`PROJECT_DISPLAY_NAMES_FIXED_FROM_SHAREPOINT_2026-06-05.md`) states:

> "No Odoo writes" — confirmed.
> "No SharePoint writes" — confirmed.

This means the "alignment" was applied **only** to:
- `docs/config/project_source_mapping.json` (adding `display_name` and aliases)
- Frontend UI strings (replacing `PRJ-001` / `PRJ-002` with the SharePoint-derived names)
- Database `project_name` migration (back-filling empty rows from the JSON config)

**It did NOT rename the actual Odoo `project.project` records.** Therefore, the Odoo project names remain unchanged and do **not** match the SharePoint display names.

---

## 8. Remaining Blockers

| # | Blocker | Impact | Owner |
|---|---------|--------|-------|
| 1 | Odoo project names do not match SharePoint display names | Prevents automatic exact-name linking | Operator / Odoo admin |
| 2 | Real mailbox addresses for PRJ-001 / PRJ-002 are still placeholders | Gate 4 cannot start | Operator |
| 3 | `User.Read.All` is missing from Graph token | Blocks Microsoft user lookup for follower-name matching | Operator / Entra admin |

---

## 9. What Exact Manual Confirmation Is Still Needed

Before any linking is recorded, the operator must:

1. **Confirm the correct Odoo project ID** for each SharePoint site (e.g., is it 14601, 14602, or another project?).
2. **Rename the Odoo project** to match the SharePoint display name **OR** add a dedicated `sharepoint_display_name` / `odoo_project_id` bridge field.
3. **Supply real mailbox SMTP addresses** for both projects so Gate 4 can proceed.
4. **Grant `User.Read.All`** if follower-name matching is ever desired as a secondary check.

---

## 10. Final Verdict

**`ODOO_SHAREPOINT_EXACT_MATCH_BLOCKED_NOT_LIVE`**

Despite the operator’s claim that project names were aligned, the read-only scan of **1,000 active Odoo projects** confirms:

- **Zero exact normalized matches** for PRJ-001.
- **Zero exact normalized matches** for PRJ-002.
- The alignment was applied **only to the config file and UI**, not to the underlying Odoo project names.
- Automatic exact-name linking is **not viable** with current data.
- Gate 4 remains blocked by unresolved mailbox placeholders.

Production remains `NOT_LIVE`. No files were modified.
