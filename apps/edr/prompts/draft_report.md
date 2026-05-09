# Draft Report Prompt

Create the schema-first executive decision report from verified evidence only.

Rules:

- Financial values must come from Odoo evidence.
- Missing values must use status `"not_available"` and value `null`.
- Every claim must carry at least one `evidence_id`.
- Every financial number must have an Odoo `evidence_id`.
- Do not invent facts, numbers, or dates.
- Do not include execution instructions in Phase 1.
- Recommendations must be marked as proposals only.
- Conflicts must be disclosed, not hidden.
- Return JSON matching the canonical report schema.
