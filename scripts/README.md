# Scripts

This directory contains operational and infrastructure utility scripts. Scripts here must stay
outside product workflow behavior unless a later phase explicitly authorizes that work.

| Script | Purpose |
|---|---|
| `init_qdrant.py` | Idempotently creates per-project Qdrant collections using the configured `QDRANT_URL` |

## Usage

```bash
make init-qdrant
```

or, inside a configured app environment:

```bash
python scripts/init_qdrant.py --mapping docs/config/project_source_mapping.example.json
```

The current script creates collection structure only. It does not embed content, insert vectors,
perform retrieval, or implement product logic.

