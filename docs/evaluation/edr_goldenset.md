# EDR Golden Set

The golden set lives under `apps/edr/evaluation/goldenset/`. Cases must include
the user question, allowed sources, expected evidence behavior, and expected
missing-data behavior.

Current repo state: one executable JSONL example exists at
`apps/edr/evaluation/goldenset/example.jsonl`.

Required baseline: the 12 categories in `docs/evaluation/edr_test_cases.md`.
Required before go-live: at least 50 executable golden cases, per spec Section 26.1.
