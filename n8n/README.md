# n8n Workflow Placeholders

This directory contains the four connector workflow files expected by the Python connector
wrappers. They are present for naming, review, and future import structure only.

| Workflow file | Intended source | Current status | Phase to implement |
|---|---|---|---|
| `sharepoint_search.json` | Microsoft Graph / SharePoint | Placeholder with empty `nodes` array | 1C |
| `owncloud_list.json` | ownCloud WebDAV | Placeholder with empty `nodes` array | 1C |
| `email_search.json` | Microsoft Graph mail search | Placeholder with empty `nodes` array | 1C |
| `odoo_read.json` | Odoo read-only API | Placeholder with empty `nodes` array | 1C |

Do not treat these files as functional workflows. Phase 1C is responsible for real n8n workflow
implementation and schema validation against `docs/schemas/evidence-object.schema.json`.

