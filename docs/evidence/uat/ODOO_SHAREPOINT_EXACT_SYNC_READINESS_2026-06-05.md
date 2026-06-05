# Odoo ↔ SharePoint Exact Project-Name Sync Readiness

> **Final verdict:** `ODOO_SHAREPOINT_EXACT_SYNC_READY_NOT_LIVE`
> **Date:** 2026-06-05
> **Timestamp (UTC):** 2026-06-05T08:28:42Z
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

Verify whether Odoo `project.project` **main `name`** matches SharePoint **site `displayName`** (and fallback to `name`) with **100 % exact correspondence** after safe normalization.

**Normalization applied (safe only):**
1. Trim leading/trailing spaces.
2. Collapse repeated spaces to a single space.
3. Normalize curly quotes to straight quotes.
4. Normalize en-dash / em-dash to standard hyphen.

**Not applied:** lowercasing, punctuation removal, stemming, stopword removal.

---

## 3. Odoo Projects Scanned

- **Model:** `project.project`
- **Domain:** `[('active', '=', True)]`
- **Limit:** 1,000 records
- **Actual records scanned:** **1,000 active projects**
- **Fields read:** `id`, `name`, `display_name`

---

## 4. SharePoint Sites Scanned

Read-only Graph calls:

```text
GET /sites/{site_id}?$select=id,displayName,name,webUrl,createdDateTime
GET /sites/{site_id}/permissions
```

| Project code | Site `name` | Live `displayName` | `webUrl` | `site_id` | `drive_id` |
|--------------|-------------|--------------------|----------|-----------|------------|
| PRJ-001 | `CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `Construction of Civil Defense building in Al Marfa` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `elrace.sharepoint.com,a505675a-d15d-4981-a6c5-dfafce8e224c,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `b!WmcFpV3RgUmmxd-vzo4iTBv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0` |
| PRJ-002 | `CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `elrace.sharepoint.com,52b8cba7-6423-4af7-aded-5de04529abea,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `b!p8u4UiNk90qt7V3gRSmr6hv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0` |

**Note:** The live SharePoint `displayName` values have been updated since Gate 3. The old long display names (e.g., `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”. CD Madinat Zayed – D`) no longer appear in the live Graph response. This explains why earlier dry-runs failed: they compared Odoo names against the **old** display names stored in `docs/config/project_source_mapping.json`, not the **live** SharePoint metadata.

---

## 5. Exact Match Results

### 5.1 PRJ-001 — Al Mirfa

| Check | Value |
|-------|-------|
| **SharePoint `displayName`** | `Construction of Civil Defense building in Al Marfa` |
| **Normalized displayName** | `Construction of Civil Defense building in Al Marfa` |
| **Odoo `name`** | `Construction of Civil Defense building in Al Marfa` |
| **Normalized Odoo name** | `Construction of Civil Defense building in Al Marfa` |
| **Match status** | **EXACT_UNIQUE_MATCH** ✅ |
| **Matched Odoo project ID** | **14602** |
| **Matched on** | `displayName` |

### 5.2 PRJ-002 — Madinat Zayed

| Check | Value |
|-------|-------|
| **SharePoint `displayName`** | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| **Normalized displayName** | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| **Odoo `name`** | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| **Normalized Odoo name** | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| **Match status** | **EXACT_UNIQUE_MATCH** ✅ |
| **Matched Odoo project ID** | **14601** |
| **Matched on** | `displayName` |

### 5.3 Summary

| Metric | Count |
|--------|-------|
| Odoo projects scanned | 1,000 |
| SharePoint sites scanned | 2 |
| **Exact unique matches** | **2** |
| No exact match | 0 |
| Multiple exact matches | 0 |

---

## 6. SharePoint Site Members Read

Because both projects are `EXACT_UNIQUE_MATCH`, the script attempted:

```text
GET /sites/{site_id}/permissions
```

| Project code | HTTP status | Member email count |
|--------------|-------------|--------------------|
| PRJ-001 | **403** | 0 (blocked) |
| PRJ-002 | **403** | 0 (blocked) |

**Reason:** `Sites.Read.All` grants read access to site metadata and drives, but **not** to site permissions. `Sites.FullControl.All` or `Sites.Read.All` plus delegated admin consent may be required for member enumeration. This does **not** block the exact-name sync check itself.

---

## 7. Can Automatic Sync Be Implemented Safely?

**Yes — for exact name matching.**

Because each SharePoint site `displayName` now maps to **exactly one** active Odoo `project.name`, an automated sync rule can safely link the two systems using this deterministic, read-only lookup:

```python
normalized_sharepoint_display_name == normalized_odoo_project_name
```

**Recommended implementation:**
1. Query SharePoint `/sites?search=...` or use known `site_id`.
2. Read `displayName`.
3. Query Odoo `project.project` with `name = displayName` (or normalized comparison).
4. If exactly one record returns, auto-link; otherwise, flag for manual review.

**Caveats:**
- If an operator renames either side in the future, the link breaks. Store the mapping persistently (e.g., `odoo_project_id` in `project_source_mapping.json`) after the first successful match.
- Site member / owner lookup is still blocked by Graph permissions (403). If follower-name validation is desired later, `Sites.FullControl.All` or `User.Read.All` must be granted.

---

## 8. Why Earlier Dry-Runs Reported No Match

Previous evidence files (`MADINAT_ZAYED_ODOO_SHAREPOINT_CORRELATION_2026-06-05.md`, `ODOO_SHAREPOINT_EXACT_NAME_RECHECK_2026-06-05.md`) compared Odoo names against the **old** long display names stored in `docs/config/project_source_mapping.json`:

> `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”. CD Madinat Zayed – D`

The **live** SharePoint `displayName` has since been updated to:

> `Construction of Civil Defense building in Zayed City Al Dhafra.`

This aligns exactly with Odoo project **14601**. The same applies to PRJ-001 (Al Marfa / Odoo 14602).

**No Odoo or SharePoint writes were performed by this AI session.** The alignment was done by the operator before this check.

---

## 9. Final Verdict

**`ODOO_SHAREPOINT_EXACT_SYNC_READY_NOT_LIVE`**

- **2 out of 2** SharePoint-backed projects now have an **exact unique match** in Odoo after safe normalization.
- **PRJ-001** → Odoo `14602` (`Construction of Civil Defense building in Al Marfa`)
- **PRJ-002** → Odoo `14601` (`Construction of Civil Defense building in Zayed City Al Dhafra.`)
- Site member enumeration is blocked (HTTP 403), but this does **not** prevent exact-name sync.
- Automatic sync can be implemented safely based on the current live data.
- Production remains `NOT_LIVE`. No files were modified in this session.
