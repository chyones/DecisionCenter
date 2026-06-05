# Madinat Zayed — Odoo ↔ SharePoint Correlation Dry-Run

> **Final verdict:** `MADINAT_ZAYED_CORRELATION_NO_MATCH_NOT_LIVE`
> **Date:** 2026-06-05
> **Timestamp (UTC):** 2026-06-05T06:51:39Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** `main` tracking `origin/main`
> **Production status:** NOT_LIVE
> **Gate 4:** Blocked (not started)
> **Slice 6 UAT:** Not started
> **Slice 7:** Not started

---

## 1. Git State

| Item | Value |
|------|-------|
| `git rev-parse HEAD` | `fc54c64cd37adb234c01296bf34dd89274196602` |
| `git status --short --branch` | `main...origin/main` with unstaged connector/node/frontend changes and untracked evidence files |

---

## 2. Target Names Searched

### 2.1 Full project name

```text
Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”
```

### 2.2 Short SharePoint / manual label

```text
CD Madinat Zayed – D
```

### 2.3 Existing SharePoint candidate

```text
CivilDefenseCenterinIndustrialAreaofMadinatZayed
```

---

## 3. Odoo Candidates

### 3.1 Search terms used (read-only `ilike` on `project.project`)

- `Construction of Civil Defense Center in Industrial Area of Madinat Zayed`
- `Madinat Zayed`
- `Civil Defense Center`
- `Al Dhafra`
- `Type D`
- `CD Madinat Zayed`

### 3.2 Results summary

- **Total Odoo candidates returned:** 73 active projects
- **Follower names successfully pulled:** Yes (via `res.partner.read`)

### 3.3 Top Odoo candidates by sequence similarity

| Odoo ID | Odoo project name | Follower count | Assigned user | Partner / Customer |
|---------|-------------------|----------------|---------------|--------------------|
| 14601 | `Construction of Civil Defense building in Zayed City Al Dhafra.` | 2 | Ahmad Ezzat Anwar | Abu Dhabi Police |
| 14344 | `old madinat zayed civil defence` | 1 | Mohamed Mamoun Orfali | Abu Dhabi Civil Defense Authority (ADCDA) |
| 13015 | `Medical Storage Madinat Zayed` | 1 | Aly Mahmoud Noureldin | Abu Dhabi Civil Defense Authority (ADCDA) |
| 15138 | `Bazar Matket Madinat Zayed` | 1 | Aly Mahmoud Noureldin | Provis Integrated Management Services - Sole Proprietorship LLC. |
| 13951 | `Madinat Zayed Wedding Hall ( Male )` | 1 | (not assigned) | (not assigned) |
| 13899 | `GENERAL MAINTENANCE MADINAT ZAYED-NEW -` | 1 | Mohamed Mamoun Orfali | Abu Dhabi Civil Defense Authority (ADCDA) |
| 13520 | `J1190 - Madinat Zayed Fodder Distribution` | 1 | Mohamed Mamoun Orfali | Provis Integrated Management Services - Sole Proprietorship LLC. [CLOSED] |
| 13622 | `Weapons store // Madinat Zayed //Al Dhafra region` | 1 | Ahmad Ezzat Anwar | Abu Dhabi Police |
| 11679 | `Construction of Civilian Protection Offices - Al Dhafra` | 0 | Aly Mahmoud Noureldin | Abu Dhabi Civil Defense Authority (ADCDA) |
| 12783 | `General Maintenance of madinat zayed Civil Denfense Project` | 2 | Aly Mahmoud Noureldin | Abu Dhabi Civil Defense Authority (ADCDA) |

*All 73 candidates are active (`active = true`).*

---

## 4. SharePoint Candidates

### 4.1 Search terms used (Graph `/sites?search=...`)

- `Madinat Zayed`
- `CivilDefenseCenterinIndustrialAreaofMadinatZayed`
- `Civil Defense Center`
- `Al Dhafra`
- `CD Madinat Zayed`

### 4.2 Results summary

| Site ID (redacted format) | `name` | `displayName` | `webUrl` | `createdDateTime` |
|---------------------------|--------|---------------|----------|-------------------|
| `elrace.sharepoint.com,52b8cba7-6423-4af7-aded-5de04529abea,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”. CD Madinat Zayed – D` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `2025-12-15T08:20:33Z` |
| `elrace.sharepoint.com,a505675a-d15d-4981-a6c5-dfafce8e224c,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type “D”. CD Al Mirfa – D` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `2025-12-15T10:24:20Z` |

*The second site is the PRJ-001 (Al Mirfa) site and is included here only because the search term `Civil Defense Center` also matches it.*

### 4.3 Mapped drive verification (PRJ-002)

- **Drive ID:** present in `project_source_mapping.json`
- **Root children read-only probe:** `GET /drives/{drive_id}/root/children?$top=1`
- **Result:** HTTP 200, **1 child item** present

---

## 5. Normalization Method

All names were normalized using the **exact same deterministic function** before comparison:

1. Convert to **lowercase**.
2. Replace curly quotes with straight quotes: `“”` → `"`, `‘’` → `'`.
3. Replace en-dash and em-dash with a single space: `–`, `—` → ` `.
4. Remove **all remaining punctuation** (anything that is not a word character or whitespace) and replace it with a space.
5. Collapse **any sequence of whitespace** to a single space.
6. **Trim** leading and trailing spaces.

No stopwords were removed. No stemming was applied. No fuzzy logic was used.

**Example:**

| Original | Normalized |
|----------|------------|
| `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”` | `construction of civil defense center in industrial area of madinat zayed al dhafra region type d` |
| `CD Madinat Zayed – D` | `cd madinat zayed d` |
| `CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `civildefensecenterinindustrialareaofmadinatzayed` |

---

## 6. Similarity Table — Top Odoo ↔ SharePoint Correlations

### 6.1 Against the **full project name**

| Odoo ID | Odoo name | Exact normalized | Token overlap % | Sequence similarity % | Missing key terms | Recommendation |
|---------|-----------|------------------|-----------------|----------------------|-------------------|----------------|
| 14601 | `Construction of Civil Defense building in Zayed City Al Dhafra.` | NO | 47.06 | 65.82 | `industrial area`, `madinat zayed`, `type d` | **WEAK_MATCH** |
| 13622 | `Weapons store // Madinat Zayed //Al Dhafra region` | NO | 29.41 | 55.71 | `civil defense`, `industrial area`, `type d` | **WEAK_MATCH** |
| 11679 | `Construction of Civilian Protection Offices - Al Dhafra` | NO | 22.22 | 55.03 | `civil defense`, `industrial area`, `madinat zayed`, `type d` | **WEAK_MATCH** |

### 6.2 Against the **short label** (`CD Madinat Zayed – D`)

| Odoo ID | Odoo name | Exact normalized | Token overlap % | Sequence similarity % | Missing key terms | Recommendation |
|---------|-----------|------------------|-----------------|----------------------|-------------------|----------------|
| 14344 | `old madinat zayed civil defence` | NO | 28.57 | 69.39 | `civil defense`, `industrial area`, `al dhafra`, `type d` | **WEAK_MATCH** |
| 13015 | `Medical Storage Madinat Zayed` | NO | 33.33 | 63.83 | `civil defense`, `industrial area`, `al dhafra`, `type d` | **WEAK_MATCH** |
| 15138 | `Bazar Matket Madinat Zayed` | NO | 33.33 | 63.64 | `civil defense`, `industrial area`, `al dhafra`, `type d` | **WEAK_MATCH** |
| 13951 | `Madinat Zayed Wedding Hall ( Male )` | NO | 28.57 | 61.22 | `civil defense`, `industrial area`, `al dhafra`, `type d` | **WEAK_MATCH** |

### 6.3 Against the **SharePoint site `name`** (`CivilDefenseCenterinIndustrialAreaofMadinatZayed`)

| Odoo ID | Odoo name | Exact normalized | Token overlap % | Sequence similarity % | Missing key terms | Recommendation |
|---------|-----------|------------------|-----------------|----------------------|-------------------|----------------|
| 14601 | `Construction of Civil Defense building in Zayed City Al Dhafra.` | NO | 0.0 | 65.82 | `industrial area`, `madinat zayed`, `type d` | **WEAK_MATCH** |
| 14344 | `old madinat zayed civil defence` | NO | 0.0 | 69.39 | `civil defense`, `industrial area`, `al dhafra`, `type d` | **WEAK_MATCH** |

*No correlation scored ≥ 80 % sequence similarity and ≥ 70 % token overlap, therefore no candidate qualifies as `STRONG_CANDIDATE_NEEDS_ADMIN_CONFIRMATION`.*

---

## 7. Strongest Candidate

| Attribute | Value |
|-----------|-------|
| **Odoo ID** | 14601 |
| **Odoo project name** | `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| **SharePoint name compared** | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”` |
| **Exact normalized match** | **NO** |
| **Token overlap** | **47.06 %** |
| **Sequence similarity** | **65.82 %** |
| **Key terms present** | `civil defense` ✅, `al dhafra` ✅ |
| **Key terms missing** | `industrial area` ❌, `madinat zayed` ❌, `type d` ❌ |
| **Recommendation** | **WEAK_MATCH** |

---

## 8. Follower Pull Result (Strongest Candidate Only)

| Attribute | Value |
|-----------|-------|
| **Odoo project** | 14601 — `Construction of Civil Defense building in Zayed City Al Dhafra.` |
| **Follower count** | 2 |
| **Follower names** | `Aly Mahmoud Noureldin`, `Ahmad Ezzat Anwar` |
| **Pull method** | `message_partner_ids` → `res.partner.read` (read-only) |
| **Odoo emails used** | None — names only |

The follower-pull mechanism works correctly.

---

## 9. Is Manual Confirmation Still Required?

**Yes — mandatory.**

Even the strongest candidate (Odoo 14601) is only a **weak match** (65.82 % sequence similarity, 47.06 % token overlap) and is missing three of the five key terms (`industrial area`, `madinat zayed`, `type d`). No exact normalized match exists among the 73 Odoo candidates against any of the three target names.

**Do not auto-confirm mapping.** An admin must manually inspect Odoo project 14601 (and any other candidate the business believes is correct) before any mapping is recorded.

---

## 10. Conclusions

| Question | Answer |
|----------|--------|
| Does the target project exist in SharePoint? | **Yes** — site `CivilDefenseCenterinIndustrialAreaofMadinatZayed` is live and readable. |
| Does the target project exist in Odoo with an exact matching name? | **No** — none of the 73 candidates match exactly. |
| Is there a strong candidate (>80 % seq + >70 % token)? | **No** — the best is 65.82 % / 47.06 %. |
| Is the strict exact-mapping plan viable for this project? | **No** — naming mismatch prevents automatic exact correlation. |

---

## 11. Final Verdict

**`MADINAT_ZAYED_CORRELATION_NO_MATCH_NOT_LIVE`**

The SharePoint site for the Madinat Zayed civil-defense project exists and is accessible, but no Odoo project name matches it exactly or even strongly enough to be considered a confirmed candidate under strict exact-normalized rules. The strongest Odoo project (14601) shares only partial token overlap and misses critical key terms. Production remains `NOT_LIVE`. No files were modified.
