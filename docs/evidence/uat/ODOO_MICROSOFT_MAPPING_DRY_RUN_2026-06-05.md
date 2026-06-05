# Odoo-to-Microsoft Strict Mapping — Read-Only Feasibility Dry-Run

> **Final verdict:** `ODOO_MICROSOFT_MAPPING_DRY_RUN_BLOCKED_NEEDS_USER_READ_ALL_NOT_LIVE`
> **Date:** 2026-06-05
> **Timestamp (UTC):** 2026-06-05T06:33:21Z
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

## 2. Current Mapping Loaded

File: `docs/config/project_source_mapping.json`

| Project | SharePoint site ID | Drive ID |
|---------|-------------------|----------|
| PRJ-001 | `elrace.sharepoint.com,a505675a-d15d-4981-a6c5-dfafce8e224c,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `b!WmcFpV3RgUmmxd-vzo4iTBv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0` |
| PRJ-002 | `elrace.sharepoint.com,52b8cba7-6423-4af7-aded-5de04529abea,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `b!p8u4UiNk90qt7V3gRSmr6hv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0` |

Email placeholders remain unresolved (not relevant to this dry-run).

---

## 3. SharePoint Sites Inspected

Read-only Graph calls:

```text
GET /sites/{site_id}?$select=id,displayName,webUrl,name
```

| Project | Site `name` | Site `displayName` | `webUrl` |
|---------|-------------|-------------------|----------|
| PRJ-001 | `CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type “D”. CD Al Mirfa – D` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` |
| PRJ-002 | `CivilDefenseCenterinIndustrialAreaofMadinatZayed` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type “D”. CD Madinat Zayed – D` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed` |

Both sites returned HTTP 200. `Sites.Read.All` is confirmed present in the token.

---

## 4. Odoo Projects Inspected

### 4.1 Authentication & query capability

- Odoo URL / database / username / API key verified from `.env`.
- Authentication succeeded (`uid` obtained).
- `project.project` `fields_get` succeeded.
- `search_read` on active projects succeeded.

### 4.2 Project universe

- Total active projects readable: **500+** (search_read capped at 500; at least 500 exist).
- Keyword candidate projects inspected: **43** (searched by `Mirfa`, `Madinat Zayed`, `Civil Defense`, `CD Al Mirfa`, `CD Madinat Zayed`).

### 4.3 Odoo project fields available

Relevant fields returned by Odoo for `project.project`:

- `id`
- `name`
- `display_name`
- `user_id` (assigned user, many2one → res.users)
- `partner_id` (customer partner, many2one → res.partner)
- `message_partner_ids` (followers, many2many → res.partner)
- `message_follower_ids` (follower records, not used directly)

No `code` field exists on `project.project` in this Odoo instance.

### 4.4 Follower pull capability

For each inspected project, follower names were successfully pulled via `res.partner.read`:

- **Follower names retrieved:** Yes (e.g., `Mohamed Mabrouk Mohamed Abdeltawwab`, `Haroon Atta`, `Hassan Mohamed M Abuebeid`, etc.)
- **Assigned user names retrieved:** Yes
- **Partner/customer names retrieved:** Yes

The follower-pull mechanism works; however, because no target project was matched, follower data for PRJ-001 and PRJ-002 specifically could not be obtained.

---

## 5. Exact Project-Name Match Results

### Normalization rule

Exact normalized match means:
1. Lowercase both strings.
2. Collapse all whitespace sequences to a single space.
3. Trim leading/trailing spaces.
4. Compare for equality.

### Reference labels from SharePoint

| Project | Reference normalized labels |
|---------|----------------------------|
| PRJ-001 | `civildefensecenterinalmirfaaldhafraregiontyped` (site name) <br> `construction of civil defense center in al mirfa, al dhafra region – type “d”. cd al mirfa – d` (displayName) <br> `cd al mirfa` (manual label) <br> `civildefensecenterinalmirfaaldhafraregiontyped` (manual label) |
| PRJ-002 | `civildefensecenterinindustrialareaofmadinatzayed` (site name) <br> `construction of civil defense center in industrial area of madinat zayed, al dhafra region – type “d”. cd madinat zayed – d` (displayName) <br> `cd madinat zayed` (manual label) <br> `civildefensecenterinindustrialareaofmadinatzayed` (manual label) |

### Odoo candidate names checked

All 43 keyword-matched Odoo project names were normalized and compared against the four reference labels above.

**Result:**

| Exact match count | Status |
|-------------------|--------|
| 0 / 43 candidates | **NO EXACT MATCH** |

No Odoo project name exactly matches any normalized SharePoint site name, display name, or manual label.

**Conclusion:** The two SharePoint projects **were not found** in Odoo under any exact normalized name match.

---

## 6. Odoo Follower Pull Result

| Metric | Value |
|--------|-------|
| Follower names pulled for candidate projects | Yes (43 projects) |
| Follower names pulled for PRJ-001 / PRJ-002 | No — projects not identified |
| Average followers per candidate | 1–3 |

Example follower names (redacted to first + last only, no emails):

- `Mohamed Mabrouk Mohamed Abdeltawwab`
- `Haroon Atta`
- `Hassan Mohamed M Abuebeid`
- `Ahmed A A Alhamayda`
- `Ahmad Ghaleb Hussian Taha`

No email values from Odoo were used or trusted.

---

## 7. Microsoft User Lookup Capability

### Graph token roles

```json
["Sites.Read.All", "Files.Read.All", "Mail.Read"]
```

| Role | Status |
|------|--------|
| `Sites.Read.All` | Present |
| `Files.Read.All` | Present |
| `Mail.Read` | Present |
| `User.Read.All` | **Missing** |

### `/users` lookup attempt

Because `User.Read.All` is absent, the read-only directory search endpoint:

```text
GET https://graph.microsoft.com/v1.0/users?$select=id,displayName,mail,userPrincipalName&$top=999
```

returns **HTTP 403**.

**Status:** `USER_LOOKUP_BLOCKED_NEEDS_USER_READ_ALL`

No Microsoft user displayName data was retrieved, so exact follower-name matching could not be performed.

---

## 8. Exact Follower-Name Match Result

**N/A** — blocked by missing `User.Read.All`.

If `User.Read.All` were granted, the planned approach would be:

1. Fetch Microsoft users (id, displayName, mail, userPrincipalName).
2. Normalize each `displayName` (lowercase, collapse spaces, trim).
3. For each Odoo follower name (already normalized), compare:
   - exact match → `AUTO_MATCHED_EXACT`
   - zero matches → `NO_EXACT_MATCH`
   - multiple matches → `MULTIPLE_EXACT_MATCHES`

This step could not be executed.

---

## 9. Feasibility Matrix

| Criterion | PRJ-001 | PRJ-002 | Overall |
|-----------|---------|---------|---------|
| SharePoint site label known | Yes | Yes | — |
| Best Odoo project candidate | None exact | None exact | — |
| Exact project name match | **NO** | **NO** | **0 / 2** |
| Odoo followers pulled for target | No | No | 0 / 2 |
| Microsoft user lookup available | **No** | **No** | Blocked |
| Exact follower matches count | N/A | N/A | N/A |
| Unmatched follower count | N/A | N/A | N/A |
| Ambiguous follower count | N/A | N/A | N/A |
| Strict plan viable with current data | **No** | **No** | **No** |

---

## 10. Blockers

### Blocker 1 — Missing `User.Read.All`

- **Impact:** Cannot read Microsoft user directory; follower-name exact matching is impossible.
- **Resolution:** Grant admin consent for `User.Read.All` on the Entra API app registration, acquire a fresh token, and re-run this dry-run.

### Blocker 2 — No exact project name match

- **Impact:** SharePoint site names / display names do not correspond to any Odoo `project.project` name exactly.
- **Resolution options:**
  1. Rename Odoo projects to match SharePoint site names exactly.
  2. Add a custom field (e.g., `sharepoint_site_name`) to Odoo projects and populate it with the exact SharePoint name.
  3. Maintain a manual mapping table (outside of strict name matching) and accept that the strict exact-match plan is not viable with current naming.

---

## 11. Readiness Percentages

| Dimension | Readiness | Calculation |
|-----------|-----------|-------------|
| **Project-name readiness** | **0%** | 0 exact matches out of 2 required |
| **Follower-pull readiness (for targets)** | **0%** | 0 target projects identified, so 0 follower sets retrieved |
| **Follower-pull capability (mechanism)** | **100%** | Odoo `message_partner_ids` → `res.partner.read` works correctly |
| **Microsoft-user-lookup readiness** | **0%** | `User.Read.All` missing; `/users` returns 403 |
| **Overall feasibility** | **0%** | Strict exact mapping cannot proceed with missing permission and mismatched names |

---

## 12. Should Implementation Proceed?

**No.**

The strict Odoo-to-Microsoft exact-mapping plan is **not implementable today** because:

1. The directory lookup permission required for follower validation is missing.
2. The naming conventions between SharePoint sites and Odoo projects are not aligned, and no exact-match bridge exists in the current data.

Before implementation:

- **Operator must grant `User.Read.All`** and confirm it appears in the token roles.
- **Operator must reconcile naming** either by aligning Odoo project names with SharePoint names or by introducing a bridging field / manual mapping.

Only after both blockers are resolved should the strict mapping logic be coded and tested.

---

## 13. Final Verdict

**`ODOO_MICROSOFT_MAPPING_DRY_RUN_BLOCKED_NEEDS_USER_READ_ALL_NOT_LIVE`**

The dry-run confirms that:

- SharePoint sites for PRJ-001 and PRJ-002 are reachable and readable.
- Odoo project data is accessible and follower-pull mechanics work.
- **No Odoo project name exactly matches** the SharePoint site/display names for PRJ-001 or PRJ-002.
- Microsoft user directory search is **blocked** due to missing `User.Read.All`.

Because the follower-name matching dimension cannot even be tested, and the project-name dimension already fails exact alignment, the strict mapping plan is blocked. Production remains `NOT_LIVE`.
