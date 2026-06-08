# Source Mapping Real Name Discovery

**Verdict:** `SOURCE_MAPPING_REAL_NAME_DISCOVERY_PARTIAL_NOT_LIVE`
**Date:** 2026-06-05
**Timestamp (UTC):** 2026-06-05T09:48:51Z
**HEAD:** `029de7c1a63c7f1b4e47abe5cf91c892743d46db`
**Branch:** `main` tracking `origin/main`
**Production status:** `NOT_LIVE`

This was a read-only discovery run for internal codes `PRJ-001` and `PRJ-002`.
The internal codes are not treated as project names. The real project names
come from verified Odoo `project.project.name` records. SharePoint URLs were
used only as locators.

No writes were made to Odoo, SharePoint, Microsoft Graph, PostgreSQL, or
configuration files. No AI providers were called. Secrets and tokens were not
printed.

---

## 1. Current State Checks

| Check | Result |
|---|---|
| `git status --short --branch` | `## main...origin/main` before evidence file creation |
| `docker compose ps` | App, Caddy, cloudflared, MinIO, n8n, PostgreSQL, Qdrant, and Redis running |
| `curl http://127.0.0.1:8000/healthz` | HTTP 200: postgres/redis/qdrant/minio all `ok` |
| `agent_preflight.py` | Clean |
| Production state | `NOT_LIVE` |

### 1.1 Runtime `source_mappings` Rows

Read-only SQL inspected only rows for `PRJ-001` and `PRJ-002`.

| Internal code | `project_name` | `mapping_status` | Enabled sources | Runtime SharePoint state | Runtime Odoo state |
|---|---|---:|---|---|---|
| `PRJ-001` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region - Type "D". CD Al Mirfa - D` | `complete` | `sharepoint`, `owncloud`, `email`, `odoo` | `site_id=example-site-id-001`, `drive_id=example-drive-id-001`, `root_path=/Projects/PRJ-001` | `project_external_id=PRJ-001`, `project_name=""` |
| `PRJ-002` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region - Type "D". CD Madinat Zayed - D` | `complete` | `sharepoint`, `owncloud`, `email`, `odoo` | `site_id=example-site-id-002`, `drive_id=example-drive-id-002`, `root_path=/Projects/PRJ-002` | `project_external_id=PRJ-002`, `project_name=""` |

**Runtime finding:** the PostgreSQL mirror is stale for these two rows. It still
contains placeholder SharePoint IDs even though the checked-in JSON contains
real Graph site and drive IDs.

### 1.2 Checked-In JSON Mapping State

File inspected: `docs/config/project_source_mapping.json`.

| Internal code | JSON project label | JSON SharePoint site/drive | JSON placeholder findings |
|---|---|---|---|
| `PRJ-001` | `Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region - Type "D". CD Al Mirfa - D` | Real Graph `site_id` and `drive_id` present | `sharepoint.root_path=/Projects/PRJ-001`; `owncloud.base_path=/Projects/PRJ-001`; `project-prj-001@example.com`; `doc-control@example.com`; `odoo.project_external_id=PRJ-001`; contract number `CON-001` unverified |
| `PRJ-002` | `Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region - Type "D". CD Madinat Zayed - D` | Real Graph `site_id` and `drive_id` present | `sharepoint.root_path=/Projects/PRJ-002`; `owncloud.base_path=/Projects/PRJ-002`; `project-prj-002@example.com`; `doc-control-002@example.com`; `odoo.project_external_id=PRJ-002`; contract numbers `CON-002`, `CON-003` unverified |

Invalid placeholders found:

| Location | Finding |
|---|---|
| JSON + DB | `/Projects/PRJ-*` used as SharePoint/ownCloud root path |
| JSON + DB | `example.com` mailboxes |
| JSON + DB | `PRJ-001` and `PRJ-002` used as Odoo external IDs |
| DB | `example-site-id-*` and `example-drive-id-*` still present |
| DB | Odoo `project_name` empty while Odoo source is enabled |

No `example-*` literal remained in the checked-in JSON SharePoint IDs; the
runtime database still has `example-site-id-*` and `example-drive-id-*`.

---

## 2. Odoo Discovery

Protocol: Odoo XML-RPC, read-only. Methods used: `common.authenticate`,
`fields_get`, `search_count`, `search`, `read`, and `check_access_rights`.

Fields requested from `project.project`:

```text
id, name, display_name, active, user_id, partner_id,
analytic_account_id, account_id, company_id, create_date, write_date
```

Field availability:

| Field | Result |
|---|---|
| `analytic_account_id` | Exists; many2one to `account.analytic.account` |
| `account_id` | Missing on `project.project` |
| Other requested fields | Present |

### 2.1 Targeted Searches

The verified real names were found by exact `project.project.name` searches:

| Internal code | Exact search term | Count | Odoo ID |
|---|---|---:|---:|
| `PRJ-001` | `Construction of Civil Defense building in Al Marfa` | 1 | `14602` |
| `PRJ-002` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | 1 | `14601` |

Fallback `name ilike` searches were also run with the requested limited
keywords. Since exact `name` searches succeeded for both targets, fallback
results are not used to establish identity.

| Search term | Total matches | Returned IDs, limited to 20 |
|---|---:|---|
| `Civil Defense` | 24 | `11718`, `11719`, `11720`, `11721`, `12721`, `12755`, `12756`, `12757`, `12759`, `12760`, `12761`, `12916`, `13163`, `13164`, `13167`, `13172`, `13173`, `13635`, `13814`, `13822` |
| `Al Marfa` | 11 | `11770`, `11877`, `13008`, `13032`, `13055`, `13278`, `13303`, `13777`, `13814`, `14486`, `14602` |
| `Al Mirfa` | 2 | `13812`, `14185` |
| `Zayed City` | 4 | `13793`, `13931`, `14202`, `14601` |
| `Al Dhafra` | 48 | `11679`, `11779`, `11805`, `11806`, `11865`, `11866`, `12054`, `12119`, `12120`, `12197`, `12199`, `12235`, `12236`, `12246`, `12895`, `12896`, `12908`, `12915`, `13010`, `13014` |

### 2.2 Verified Odoo Records

| Internal code | Odoo project ID | `project.project.name` | Active | `user_id` | `partner_id` | Analytic/account field | Why it matches |
|---|---:|---|---|---|---|---|---|
| `PRJ-001` | `14602` | `Construction of Civil Defense building in Al Marfa` | true | `2178` - Ahmad Ezzat Anwar | `11380` - Abu Dhabi Police | `analytic_account_id=21963` | Exact `project.project.name` match |
| `PRJ-002` | `14601` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | true | `2178` - Ahmad Ezzat Anwar | `11380` - Abu Dhabi Police | `analytic_account_id=21960` | Exact `project.project.name` match |

Fallback candidates did not override these records because none was needed once
the exact Odoo names matched.

---

## 3. Analytic Account Discovery

Analytic linkage is present on `project.project.analytic_account_id`.
`project.project.account_id` does not exist.

| Internal code | Odoo project ID | Analytic account ID | Analytic account name | Analytic code |
|---|---:|---:|---|---|
| `PRJ-001` | `14602` | `21963` | `Construction of Civil Defense building in Al Marfa` | `209/2025` |
| `PRJ-002` | `14601` | `21960` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | `208/2025` |

`account.analytic.line` is readable and contains the relation fields:

| Model | Field | Relation |
|---|---|---|
| `account.analytic.line` | `account_id` | `account.analytic.account` |
| `account.analytic.line` | `project_id` | `project.project` |
| `account.analytic.line` | `general_account_id` | `account.account` |

**Cost model guidance:** keep `cost_model` as `account.analytic.line`.

---

## 4. HR / Project People Discovery

No broad HR dump was performed. Only metadata fields and target-linked users or
employees were inspected.

Relevant `project.project` people fields discovered:

| Field | Label | Relation | Guidance |
|---|---|---|---|
| `user_id` | Project Manager | `res.users` | Best source for UI Project Manager |
| `projects_manager` | Projects Manager | `hr.employee` | Can populate `Other` or a separately named Projects Manager field |
| `project_eng_id` | Civil Engineer | `hr.employee` | Can populate `Other` as project/civil engineer |
| `alias_user_id` | Owner | `res.users` | Owner-like source, requires business confirmation before mapping |
| `branch_manager_id` | Branch Manager | `hr.employee` | Field exists, empty for target records |
| `department_id` | Project Department | `hr.department` | Field exists, empty for target records |
| `architect`, `activity_user_id`, `allowed_user_ids`, `favorite_user_ids` | Various users/members | `res.users` | Not direct sources for the requested named UI fields |

Target project values:

| Internal code | Project Manager source | Projects Manager source | Project/Civil Engineer source | Owner-like source |
|---|---|---|---|---|
| `PRJ-001` | `project.project.user_id` -> `res.users(2178)` Ahmad Ezzat Anwar | `project.project.projects_manager` -> `hr.employee(738)` Aly Mahmoud Noureldin | `project.project.project_eng_id` -> `hr.employee(1878)` Numeriano suguibal Apayyo | `project.project.alias_user_id` -> `res.users(717)` Ahmed Ismail Moustafa |
| `PRJ-002` | `project.project.user_id` -> `res.users(2178)` Ahmad Ezzat Anwar | `project.project.projects_manager` -> `hr.employee(738)` Aly Mahmoud Noureldin | `project.project.project_eng_id` -> `hr.employee(1016)` Mohamed Mamoun Orfali | `project.project.alias_user_id` -> `res.users(717)` Ahmed Ismail Moustafa |

`hr.employee` read permission is available. The user linked by
`project.project.user_id` resolves to `hr.employee(2142)` with job title
`Project Manager` and department `Civil`.

Requested people fields:

| UI field | Source result |
|---|---|
| Project Manager | `project.project.user_id` -> `res.users`, optionally cross-check with `hr.employee.user_id` |
| Commercial Manager | `MISSING_SOURCE_FIELD` |
| Finance Owner | `MISSING_SOURCE_FIELD` |
| Document Controller | `MISSING_SOURCE_FIELD` |
| Other people | `project.project.projects_manager`, `project.project.project_eng_id`, and possibly `alias_user_id`; manual label confirmation required |

---

## 5. SharePoint Discovery

Protocol: Microsoft Graph read-only. Token value was not printed.

### 5.1 Direct Site Resolution

| Internal code | Graph call | Status | Site ID | Display name | Web URL |
|---|---|---:|---|---|---|
| `PRJ-001` | `GET /sites/elrace.sharepoint.com:/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` | 200 | `elrace.sharepoint.com,a505675a-d15d-4981-a6c5-dfafce8e224c,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `Construction of Civil Defense building in Al Marfa` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD` |
| `PRJ-002` | `GET /sites/elrace.sharepoint.com:/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed` | 200 | `elrace.sharepoint.com,52b8cba7-6423-4af7-aded-5de04529abea,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed` |

### 5.2 Drive Resolution

| Internal code | Graph call | Status | Drive ID | Drive name | Drive URL |
|---|---|---:|---|---|---|
| `PRJ-001` | `GET /sites/{site-id}/drives` | 200 | `b!WmcFpV3RgUmmxd-vzo4iTBv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0` | `Documents` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD/Shared%20Documents` |
| `PRJ-002` | `GET /sites/{site-id}/drives` | 200 | `b!p8u4UiNk90qt7V3gRSmr6hv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0` | `Documents` | `https://elrace.sharepoint.com/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed/Shared%20Documents` |

### 5.3 Targeted Search

| Search term | Result |
|---|---|
| `Al Marfa` | Found PRJ-001 SharePoint site |
| `Al Mirfa` | No site returned |
| `Civil Defense` | Found both PRJ-001 and PRJ-002 sites |

The SharePoint URL slugs differ from the Odoo names for both projects. This is
acceptable: Odoo `project.project.name` remains the real project name; the
SharePoint slug remains only a locator.

---

## 6. Verification Matrix

| internal_code | verified_odoo_project_id | verified_odoo_project_name | analytic_account_id | analytic_account_name | project_manager_source | sharepoint_site_id | sharepoint_displayName | sharepoint_drive_id | name_source | confidence | blockers |
|---|---:|---|---:|---|---|---|---|---|---|---|---|
| `PRJ-001` | `14602` | `Construction of Civil Defense building in Al Marfa` | `21963` | `Construction of Civil Defense building in Al Marfa` | `project.project.user_id` -> `res.users(2178)` Ahmad Ezzat Anwar | `elrace.sharepoint.com,a505675a-d15d-4981-a6c5-dfafce8e224c,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `Construction of Civil Defense building in Al Marfa` | `b!WmcFpV3RgUmmxd-vzo4iTBv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0` | `ODOO_PROJECT_NAME_VERIFIED` | High | DB mirror stale; mailboxes not verified; `root_path` placeholder; `PRJ-001` invalid as Odoo external ID |
| `PRJ-002` | `14601` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | `21960` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | `project.project.user_id` -> `res.users(2178)` Ahmad Ezzat Anwar | `elrace.sharepoint.com,52b8cba7-6423-4af7-aded-5de04529abea,26e3f61b-f187-4b70-a1d0-a0b0dccea161` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | `b!p8u4UiNk90qt7V3gRSmr6hv24yaH8XBLodCgsNzOoWHB2buVTUicS54-X7ujc_p0` | `ODOO_PROJECT_NAME_VERIFIED` | High | DB mirror stale; mailboxes not verified; `root_path` placeholder; `PRJ-002` invalid as Odoo external ID |

---

## 7. Field-by-Field Autofill Guidance

| UI field | Source system | Model/API | Exact field | Can autofill | Needs manual confirmation | Blocker |
|---|---|---|---|---|---|---|
| Project Name | Odoo | `project.project` | `name` | yes | no | none |
| Contract Numbers | Odoo | `account.analytic.account` | `code` | yes | yes | Confirm analytic code equals contract number in business usage |
| Odoo Project External ID | Odoo | `project.project` | `id` | yes | no | Current JSON/DB incorrectly use `PRJ-*` |
| Odoo Project Name | Odoo | `project.project` | `name` | yes | no | none |
| Project Model | Odoo | Static validated model | `project.project` | yes | no | none |
| Cost Model | Odoo | Static validated model | `account.analytic.line` | yes | no | none |
| SharePoint Site ID | Microsoft Graph | `GET /sites/{host}:{path}` | `id` | yes | no | Runtime DB stale |
| SharePoint Drive ID | Microsoft Graph | `GET /sites/{site-id}/drives` | `id` for `Documents` drive | yes | no | Runtime DB stale |
| SharePoint Root Path | Microsoft Graph / mapping policy | Drive root | `/` candidate for project-specific sites | yes | yes | Current `/Projects/PRJ-*` is placeholder; confirm root-vs-subfolder policy |
| Shared Mailboxes | Microsoft Graph / operator | Mailbox lookup | SMTP address | no | yes | `example.com` placeholders only |
| Document Control Mailbox | Microsoft Graph / operator | Mailbox lookup | SMTP address | no | yes | `example.com` placeholders only |
| Client Domains | Operator / email rules | Mapping config | domain strings | no | yes | `MISSING_SOURCE_FIELD` |
| Consultant Domains | Operator / email rules | Mapping config | domain strings | no | yes | `MISSING_SOURCE_FIELD` |
| Contractor Domains | Operator / email rules | Mapping config | domain strings | no | yes | `MISSING_SOURCE_FIELD` |
| Project Manager | Odoo | `project.project` -> `res.users` | `user_id` | yes | no | none |
| Commercial Manager | Odoo/HR | Not found | `MISSING_SOURCE_FIELD` | no | yes | No verified field |
| Finance Owner | Odoo/HR | Not found | `MISSING_SOURCE_FIELD` | no | yes | No verified field |
| Document Controller | Odoo/HR or Microsoft | Not found | `MISSING_SOURCE_FIELD` | no | yes | No verified field |
| Other | Odoo | `project.project` | `projects_manager`, `project_eng_id`, `alias_user_id` | yes | yes | Confirm labels before storing |
| Enabled Sources | Discovery result | Odoo + Graph + operator policy | `sharepoint`, `odoo`; email/ownCloud pending | partial | yes | Email and ownCloud coordinates not verified |

---

## 8. Blockers

| Blocker | Impact |
|---|---|
| PostgreSQL `source_mappings` mirror still has placeholder SharePoint IDs | Runtime admin mapping state does not match checked-in JSON or Graph truth |
| `PRJ-001` / `PRJ-002` used as Odoo external IDs | Invalid for Odoo linkage; should use verified Odoo IDs or another real Odoo identifier |
| `/Projects/PRJ-*` root paths | Placeholder path; Graph verified project-specific document libraries, but root policy still needs confirmation |
| Email fields use `example.com` | Email source cannot be treated as live |
| ownCloud base paths use `/Projects/PRJ-*` | ownCloud source remains unverified |
| Commercial Manager / Finance Owner / Document Controller fields not found | Cannot autofill those UI fields from current Odoo metadata |

---

## 9. API Usage Summary

Local read-only checks:

- `git status --short --branch`
- `docker compose ps`
- `curl http://127.0.0.1:8000/healthz`
- `psql` read-only `SELECT` against `source_mappings` for `PRJ-001` and `PRJ-002`
- `sed`/`rg` reads of repo docs and source

Odoo XML-RPC read-only calls:

- `common.authenticate`
- `project.project.fields_get`
- `project.project.search_count`
- `project.project.search`
- `project.project.read`
- `account.analytic.account.fields_get/read`
- `account.analytic.line.fields_get`
- `res.users.read`
- `hr.employee.check_access_rights`
- `hr.employee.search/read` for target-linked `user_id`

Microsoft Graph read-only calls:

- Token acquisition via configured client credentials; token not printed
- `GET /sites/elrace.sharepoint.com:/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD`
- `GET /sites/elrace.sharepoint.com:/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed`
- `GET /sites/{site-id}/drives`
- `GET /sites?search=Al Marfa`
- `GET /sites?search=Al Mirfa`
- `GET /sites?search=Civil Defense`

No Odoo, SharePoint, Microsoft Graph, PostgreSQL, or config writes were made.

---

## 10. Conclusion

Real project names and the Odoo-to-SharePoint links are verified:

| Internal code | Real Odoo project name | Odoo ID | SharePoint site verified | Drive verified |
|---|---|---:|---|---|
| `PRJ-001` | `Construction of Civil Defense building in Al Marfa` | `14602` | yes | yes |
| `PRJ-002` | `Construction of Civil Defense building in Zayed City Al Dhafra.` | `14601` | yes | yes |

The discovery itself succeeded for the real-name and SharePoint-link objective,
but the verdict remains partial because runtime mapping state is stale and
several non-name fields remain placeholders or missing.

Final verdict:

```text
SOURCE_MAPPING_REAL_NAME_DISCOVERY_PARTIAL_NOT_LIVE
```

Production remains `NOT_LIVE`.
