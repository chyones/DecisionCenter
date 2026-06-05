# Madinat Zayed — Odoo ↔ SharePoint Linking Method Research

> **Final verdict:** `MADINAT_ZAYED_LINKING_METHOD_RESEARCH_COMPLETE_NOT_LIVE`
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

## 2. ⚠️ PRJ-002 Trustworthiness Assessment

**Conclusion:** `UNKNOWN_DO_NOT_TRUST` — likely test / internal / AI-added fixture.

### Evidence from repo

| Source | How PRJ-002 is used |
|--------|---------------------|
| `docs/config/project_source_mapping.json` | Mapping entry with real SharePoint site/drive IDs but **placeholder email addresses** (`project-prj-002@example.com`, `doc-control-002@example.com`). |
| `docs/config/project_source_mapping.example.json` | Same placeholder structure. |
| `apps/edr/tests/integration/test_phase2b_source_mapping.py` | Hard-coded test fixture (`project_code: "PRJ-002"`). |
| `apps/edr/tests/integration/test_phase2a_backend.py` | Test assertions expect `PRJ-002` in allowed-projects list. |
| `apps/edr/tests/integration/test_phase2b_approvals.py` | Test payload uses `PRJ-002`. |
| `frontend/e2e/accessibility.spec.ts` | Dummy UI data (`{ project_code: 'PRJ-002', display_name: 'Test Project 2' }`). |
| `apps/edr/evaluation/goldenset/goldenset.jsonl` | Evaluation case references `PRJ-002`. |
| `docs/design/UI_CONTRACT_v1.md` | Mock UI screenshots use `PRJ-002` as placeholder. |
| `docs/evidence/uat/` | No operator-signed business confirmation that `PRJ-002` is a real contract or project code. Gate 3 evidence records operator setting SharePoint coordinates, but does not confirm the code itself is a business truth. |

**Assessment:** `PRJ-002` is pervasive in **tests, design mocks, and evaluation data**. It has **never been proven** as a real business project code (no contract document, no ERP reference, no operator sign-off). The mapping config uses it as a container for SharePoint coordinates, but the email placeholders remain unresolved, which is consistent with a **fixture rather than a live project record**.

**Research directive:** This report treats `PRJ-002` as **untrusted** and searches for the **real** Odoo project that should link to the Madinat Zayed SharePoint site.

---

## 3. Target Project

```text
Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”. CD Madinat Zayed – D
```

**SharePoint site `name`:** `CivilDefenseCenterinIndustrialAreaofMadinatZayed`

---

## 4. Odoo Candidates (Read-Only Search)

### 4.1 Search terms used

- `Construction of Civil Defense Center in Industrial Area of Madinat Zayed`
- `Civil Defense Center`
- `Industrial Area`
- `Madinat Zayed`
- `Zayed City`
- `Al Dhafra`
- `Type D`
- `CD Madinat Zayed`
- `Civil Defense building`

### 4.2 Results summary

- **Total active Odoo candidates returned:** 77 projects
- **Odoo `project.project` fields available:** 272 fields (including `project_code`, `analytic_account_id`, `create_date`, `write_date`, etc.)

### 4.3 Top Odoo candidates (by similarity + data richness)

| Odoo ID | Project name | `project_code` | Customer / Partner | Assigned user | Followers | Create date | Write date | Analytic account hint |
|---------|--------------|----------------|--------------------|---------------|-----------|-------------|------------|-----------------------|
| **14601** | `Construction of Civil Defense building in Zayed City Al Dhafra.` | **208/2025** | Abu Dhabi Police | Ahmad Ezzat Anwar | 2 | 2025-12-21 | 2026-05-08 | `[208/2025] RCC Projects / ... Construction of Civil Defense building in Zayed City Al Dhafra.` |
| 14602 | `Construction of Civil Defense building in Al Marfa` | 209-2025 | Abu Dhabi Police | Ahmad Ezzat Anwar | 2 | 2025-12-21 | 2026-06-04 | `[209/2025] RCC Projects / ... Construction of Civil Defense building in Al Marfa` |
| 14344 | `old madinat zayed civil defence` | 202410101-2025 | Abu Dhabi Civil Defense Authority (ADCDA) | Mohamed Mamoun Orfali | 1 | 2025-05-02 | 2026-05-18 | `[ADCDA/2024/17/112] RCC Projects / Contract for Maintenance Works at Civil Defense Buildings ...` |
| 13015 | `Medical Storage Madinat Zayed` | 33/2021 | Abu Dhabi Civil Defense Authority (ADCDA) | Aly Mahmoud Noureldin | 1 | 2023-05-30 | 2026-05-08 | `[Pending] RCC Projects / Contract for Maintenance Works ...` |
| 15138 | `Bazar Matket Madinat Zayed` | P/2022/SP/C/032/B3 | Provis Integrated Management Services | Aly Mahmoud Noureldin | 1 | 2026-05-08 | 2026-05-24 | `[160:150] RCC Projects / Blanket Agreement ...` |
| 13899 | `GENERAL MAINTENANCE MADINAT ZAYED-NEW -` | 33/2021 | Abu Dhabi Civil Defense Authority (ADCDA) | Mohamed Mamoun Orfali | 1 | 2024-08-28 | 2026-05-18 | `[ADCDA/2021/172] RCC Projects / Contract for Maintenance Works ...` |
| 13622 | `Weapons store // Madinat Zayed //Al Dhafra region` | 25/2023 | Abu Dhabi Police | Ahmad Ezzat Anwar | 1 | 2024-03-01 | 2026-05-18 | `[Pending] RCC Projects / Execution and Implementations of Work Orders ...` |
| 13520 | `J1190 - Madinat Zayed Fodder Distribution` | PD/CA/FM/MH/R1467/GENERAL-/20/102 | Provis Integrated Management Services [CLOSED] | Mohamed Mamoun Orfali | 1 | 2024-01-14 | 2026-05-08 | `[WOCM58:118] HCI Projects / Comprehensive Services Agreement ...` |
| 12916 | `2022/77/311904-7237 Construction of Civil Defense Center HATTA / Dubai` | 2022/77/311904-7237 | Ministry of Energy and Infrastructure | Kamroddin Syed Khader Syed | 4 | 2023-04-07 | 2026-05-08 | `[2022/77/311904-7237] RCC Projects / Construction of Civil Defense Center HATTA ...` |

### 4.4 Key observation — `project_code` field

Odoo project **14601** carries a structured `project_code`: `208/2025`. This is a **real reference number** that appears in the analytic account name and could be used as a bridging key. None of the other candidates have a code that appears in the SharePoint site metadata, but the existence of `project_code` proves Odoo can store an external reference.

---

## 5. SharePoint Candidates (Read-Only Graph)

### 5.1 Search terms used

- `Madinat Zayed`
- `CivilDefenseCenterinIndustrialAreaofMadinatZayed`
- `Civil Defense Center`
- `Al Dhafra`
- `CD Madinat Zayed`

### 5.2 Results

| Site `name` | `displayName` | `webUrl` | `createdDateTime` |
|-------------|---------------|----------|-------------------|
| `CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”. CD Madinat Zayed – D` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `2025-12-15T08:20:33Z` |
| `CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type “D”. CD Al Mirfa – D` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `2025-12-15T10:24:20Z` |

Only the first site is relevant to this research.

### 5.3 Drive contents (root children)

The mapped drive for PRJ-002 (the Madinat Zayed site) contains **28 root folders**:

```text
00. Close-Out Files
01. QHSE Files
1. Pre Qualification
10. Work Inspection Request
11. Programs & Schedules
12. Safety
13. Site Photographs
14. SOR & NCR
15. Other Certifications
16. Administration
17. Correspondence
18. Minutes of Meeting
19. Daily Reports
2. Material Submittal
20. Monthly Reports
21. Log
22. Payment Certificate
3. Shop Drawings & Calculations
4. Method Statement and Risk Assessment
5. Sample Tag
6. Document Submittal
7. Test Report
8. Request For Information
9. Material Inspection Request
BOQ
CD DRM Stamped Drawings
IFC Drawing
```

**Folder-structure hint:** The folder `CD DRM Stamped Drawings` contains the abbreviation **CD** (Civil Defense), which aligns with the project domain. No folder name contains `208/2025`, `Zayed City`, or an Odoo project ID.

### 5.4 Site permissions / owners

```text
GET /sites/{site_id}/permissions
```

- **Result:** HTTP 403
- **Implication:** `Sites.Read.All` is insufficient for reading site membership. `Sites.FullControl.All` or `User.Read.All` would be required. This research **did not obtain** owner/member lists.

---

## 6. Normalization Method

All string comparisons used this deterministic, transparent normalization:

1. Lowercase.
2. Replace curly quotes with straight quotes.
3. Replace en-dash / em-dash with a single space.
4. Remove all remaining punctuation (replace with space).
5. Collapse whitespace sequences to a single space.
6. Trim ends.

No stopwords were removed. No stemming was applied.

---

## 7. Candidate Comparison Table

### 7.1 Odoo 14601 vs target SharePoint site

| Anchor | Odoo 14601 | SharePoint site | Match? |
|--------|------------|-----------------|--------|
| **Exact normalized full name** | `construction of civil defense building in zayed city al dhafra` | `construction of civil defense center in industrial area of madinat zayed al dhafra region type d cd madinat zayed d` | **NO** |
| **Token overlap** | — | — | **47.06 %** |
| **Sequence similarity** | — | — | **65.82 %** |
| **Key term `civil defense`** | ✅ | ✅ | Match |
| **Key term `industrial area`** | ❌ | ✅ | Missing in Odoo |
| **Key term `madinat zayed`** | ❌ | ✅ | Missing in Odoo |
| **Key term `al dhafra`** | ✅ | ✅ | Match |
| **Key term `type d`** | ❌ | ✅ | Missing in Odoo |
| **`project_code`** | `208/2025` | Not present in site name / displayName / folder names | No bridge |
| **Customer** | Abu Dhabi Police | Unknown from SharePoint metadata | — |
| **Assigned user** | Ahmad Ezzat Anwar | Unknown (permissions blocked) | — |
| **Followers** | Aly Mahmoud Noureldin, Ahmad Ezzat Anwar | Unknown (permissions blocked) | — |
| **Confidence** | — | — | **WEAK_NEEDS_MANUAL_BRIDGE** |

### 7.2 Other notable candidates

| Odoo ID | vs SharePoint displayName | Token overlap | Seq sim | Missing key terms | Confidence |
|---------|---------------------------|---------------|---------|-------------------|------------|
| 14344 | `old madinat zayed civil defence` | 0.0 % | 69.39 % | `civil defense` (form mismatch), `industrial area`, `al dhafra`, `type d` | WEAK_NEEDS_MANUAL_BRIDGE |
| 13015 | `Medical Storage Madinat Zayed` | 0.0 % | 63.83 % | `civil defense`, `industrial area`, `al dhafra`, `type d` | WEAK_NEEDS_MANUAL_BRIDGE |
| 15138 | `Bazar Matket Madinat Zayed` | 0.0 % | 63.64 % | `civil defense`, `industrial area`, `al dhafra`, `type d` | WEAK_NEEDS_MANUAL_BRIDGE |
| 13899 | `GENERAL MAINTENANCE MADINAT ZAYED-NEW -` | 0.0 % | 58.18 % | `civil defense`, `industrial area`, `al dhafra`, `type d` | WEAK_NEEDS_MANUAL_BRIDGE |
| 12783 | `General Maintenance of madinat zayed Civil Denfense Project` | 29.41 % | 55.71 % | `industrial area`, `type d` | WEAK_NEEDS_MANUAL_BRIDGE |

**No candidate achieves `EXACT_CONFIRMED` or `STRONG_NEEDS_CONFIRMATION`.**

---

## 8. Linking Strategy Evaluation

| Strategy | Required data | Current feasibility | Risk | Manual work | Scales? | Supports Gate 4? | Recommendation |
|----------|---------------|---------------------|------|-------------|---------|------------------|----------------|
| **1. Exact name matching only** | Identical normalized strings | **0 %** — no exact match exists | Low | None | Yes | No | ❌ **Not viable** |
| **2. Project reference / contract field bridge** | `project_code` in Odoo + same code stored in SharePoint metadata or folder name | **Low** — Odoo has `208/2025`, but SharePoint site/folders do not contain it | Medium | Add reference field to SharePoint or map table | Yes, if standardized | Yes, if code is reliable | ⚠️ **Possible after operator adds reference** |
| **3. Manual Odoo project ID bridge** | Odoo `id` (e.g., 14601) manually paired with SharePoint `site_id` | **100 %** — works immediately | Very low | One-time manual mapping per project | Does not auto-scale | Yes | ✅ **Best immediate option** |
| **4. Odoo follower → Microsoft user exact match** | `User.Read.All` + exact `displayName` match | **Blocked** — `User.Read.All` missing; even if present, names may not be unique | High | Name normalization + dedup | No | No | ❌ **Blocked and unreliable** |
| **5. SharePoint site aliases stored in mapping** | Add `odoo_project_id` or `aliases` array to `project_source_mapping.json` | **100 %** — config-only change | Low | One-time data entry | Yes, if maintained | Yes | ✅ **Best long-term option** |
| **6. Rename SharePoint site/displayName to match Odoo** | Write access to SharePoint + business approval | **Possible** but requires write ops and may break existing bookmarks/links | High | Rename site, update all references | No | No | ⚠️ **High risk, not recommended** |
| **7. Rename/standardize Odoo project names to match SharePoint** | Write access to Odoo + business approval | **Possible** but may break accounting/analytic links | High | Rename projects, retrain users | No | No | ⚠️ **High risk, not recommended** |

---

## 9. Best Recommended Linking Method

**Hybrid: Strategy 3 (Manual ID bridge) + Strategy 5 (Site aliases in mapping).**

### Immediate step (today)

1. **Manually confirm** with the project admin / operator that Odoo project **14601** (`Construction of Civil Defense building in Zayed City Al Dhafra.`, code `208/2025`) is the correct business record for the Madinat Zayed Civil Defense Center.
2. **Add an explicit `odoo_project_id` field** (or `odoo_project_code`) to `docs/config/project_source_mapping.json` for this entry:
   ```json
   {
     "project_code": "PRJ-002",
     "odoo_project_id": 14601,
     "odoo_project_code": "208/2025",
     "sharepoint": { ... }
   }
   ```
3. **Do not rely on PRJ-002** as the business identity; keep it only as an internal reference label if needed, but treat the mapping as a **manual bridge**.

### Future step (after operator agreement)

4. If the business wants **automatic linking**, introduce a `project_reference` field in SharePoint (e.g., a site column or document library metadata) populated with `208/2025`. Then the connector can query SharePoint by that reference and match it to Odoo `project_code`. This is Strategy 2 and scales well.

---

## 10. Why Automatic Exact Matching Should Not Be Used

- **Zero exact matches:** None of the 77 Odoo candidates match the SharePoint displayName or site name exactly after normalization.
- **Weak similarities are misleading:** The best candidate (14601) is only 65.82 % sequence similar and misses three of five key terms (`industrial area`, `madinat zayed`, `type d`).
- **Risk of false positives:** Auto-linking by fuzzy or token overlap could map the wrong project (e.g., 14602 is Al Marfa, a different location).
- **Business liability:** Linking the wrong Odoo project to a SharePoint site would cause incorrect evidence retrieval, wrong cost data, and faulty reports.

**Decision:** Automatic exact matching is **not viable** for this project today.

---

## 11. What Exact Manual Confirmation Is Needed

The operator / project admin must answer **all** of the following before any linking is recorded:

1. **Is Odoo project 14601 (`208/2025`) the correct project** for the Madinat Zayed Civil Defense Center?
2. **Is `PRJ-002` a real business project code**, or should it be replaced with `208/2025` (or another real code)?
3. **Should the SharePoint site displayName** be updated to match the Odoo project name, or vice-versa?
4. **Are the Odoo follower names** (`Aly Mahmoud Noureldin`, `Ahmad Ezzat Anwar`) the same people who own the SharePoint site? (Requires `User.Read.All` to verify.)
5. **Should a `project_reference` field** be added to SharePoint to store the Odoo `project_code` (`208/2025`) for future automation?

Until these questions are answered, **no automatic linking should be implemented**.

---

## 12. Is `User.Read.All` Required?

**Yes, for strategies 4 and 5 (user-based matching), but not for the recommended manual ID bridge.**

| Use case | Requires `User.Read.All`? |
|----------|---------------------------|
| Manual Odoo ID → SharePoint site mapping | **No** |
| Follower-name → Microsoft `displayName` exact match | **Yes** |
| SharePoint site owner/member comparison | **Yes** (or `Sites.FullControl.All`) |
| Project reference field automation | **No** |

Current token roles: `Sites.Read.All`, `Files.Read.All`, `Mail.Read`. `User.Read.All` is **missing**.

---

## 13. Can Gate 4 Proceed After This Research?

**No — this research does not unblock Gate 4.**

Gate 4 is blocked by **missing real mailbox addresses** for the project placeholders (`project-prj-002@example.com`, `doc-control-002@example.com`). This research was about **Odoo-to-SharePoint linking**, not about email mapping. The two blockers are independent:

| Blocker | Status | Owner |
|---------|--------|-------|
| Real shared mailbox SMTP for PRJ-002 | **Open** | Operator |
| Real doc-control mailbox SMTP for PRJ-002 | **Open** | Operator |
| Odoo ↔ SharePoint linking method | **Resolved** (manual ID bridge recommended) | AI / Operator confirmation |

Gate 4 can proceed **only after** the operator supplies the four real SMTP addresses (PRJ-001 + PRJ-002) and confirms the Odoo project ID mapping.

---

## 14. Final Verdict

**`MADINAT_ZAYED_LINKING_METHOD_RESEARCH_COMPLETE_NOT_LIVE`**

This research concludes that:

1. **PRJ-002 is untrusted** — it appears only in tests, mocks, and placeholder configs with no business confirmation.
2. **The best Odoo candidate is project 14601** (`Construction of Civil Defense building in Zayed City Al Dhafra.`, code `208/2025`), but it is only a **weak match** to the SharePoint site name.
3. **No automatic exact linking is viable** with current data.
4. **The strongest practical method is a manual Odoo project ID bridge** (store `odoo_project_id` and `odoo_project_code` in the mapping config).
5. **`User.Read.All` is not required** for the recommended method, but would be needed for any user-name-based matching.
6. **Gate 4 remains blocked** by missing mailbox addresses, independent of this linking research.

Production remains `NOT_LIVE`. No files were modified.
