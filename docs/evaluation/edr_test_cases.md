# EDR Test Cases

> **Authoritative source:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md` Section 26.1.

The locked spec defines 12 required baseline test-case categories. This file lists the
categories only; it does not claim that executable golden cases already exist.

## Required Baseline Categories

1. Budget vs Actual question with complete Odoo data.
2. Budget vs Actual question with missing Odoo data.
3. Delay question with email evidence.
4. Delay question with conflicting email and letter evidence.
5. Claim question with formal notice.
6. Contract risk question with missing contract.
7. Procurement question with missing PO.
8. Unauthorized project access attempt.
9. Unauthorized mailbox access attempt.
10. Prompt injection inside document.
11. Duplicate document revisions.
12. Conflicting invoice and Odoo amount.

## Current Executable Golden Set

Only one executable JSONL example currently exists:

- `apps/edr/evaluation/goldenset/example.jsonl`

No missing golden cases are faked in this repository state.

## Required Counts

| Milestone | Required Count | Current Count | Status |
|---|---:|---:|---|
| Before product logic is accepted | 12 baseline categories documented | 12 documented here | documented-only |
| Before go-live | At least 50 executable golden cases | 1 executable JSONL example | blocked until expanded |
