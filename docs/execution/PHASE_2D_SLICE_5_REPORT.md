# Phase 2D Slice 5 — Production Hardening Readiness

## Status

**IMPLEMENTED_NOT_LIVE**

Slice 5 was explicitly approved in the current session and is now complete.

## Scope

Create and validate production hardening readiness:
- Secrets review and policy
- Environment variable readiness
- TLS/domain readiness
- Firewall exposure review
- SSH hardening checklist
- Redis/Qdrant/MinIO/PostgreSQL/n8n exposure review
- Operator hardening evidence

## Deliverables

| Deliverable | Location | Status |
|---|---|---|
| Production hardening checklist | `docs/operations/production_hardening_checklist.md` | ✅ |
| Secrets management policy | `docs/policies/secrets_policy.md` | ✅ |
| Automated hardening checker | `scripts/check_hardening.py` | ✅ |
| Integration tests | `apps/edr/tests/integration/test_phase2d_slice5_hardening.py` | ✅ |

## Hardening Coverage

### Secrets Management

- `.env` files are excluded from git (`.gitignore` + `git ls-files` verification).
- `.env.example` uses only placeholder values (`change-me`, empty strings).
- Secrets policy documents rotation procedure, leak response, and inventory.

### Environment Variable Readiness

- `.env.example` contains exactly 40 keys (enforced by CI).
- Every key in `.env.example` is loaded by `apps.edr.config.settings` (enforced by CI).
- Production values are operator-managed outside git.

### TLS and Domain

- Caddy serves `PUBLIC_HOSTNAME` with auto-TLS via ACME.
- HSTS (`max-age=31536000; includeSubDomains`), `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer` are present.
- Backend receives `X-Forwarded-Proto` for scheme-aware redirects.

### Service Exposure

| Service | Host Port | Verdict |
|---|---|---|
| `app` | `127.0.0.1:8000` | ✅ localhost only |
| `postgres` | *none* | ✅ internal only |
| `redis` | *none* | ✅ internal only |
| `qdrant` | *none* | ✅ internal only |
| `minio` | `127.0.0.1:9000/9001` | ✅ localhost only |
| `n8n` | *none* | ✅ internal only |
| `caddy` | `80:80`, `443:443` | ✅ intended public |

**No internal service is bound to `0.0.0.0` or a public interface.**

### SSH and Firewall

- SSH hardening checklist is documented (operator must verify on Hetzner host).
- Firewall (`ufw`) checklist is documented (operator must verify on Hetzner host).
- These are operator-run checks and are outside CI scope.

## Automated Check Evidence

```bash
$ python3 scripts/check_hardening.py
[PASS] .env.example placeholders: No real secrets detected
[PASS] .gitignore coverage: All required patterns present
[PASS] No committed .env files: No .env files in git index
[PASS] Internal service exposure: Only Caddy is publicly bound
[PASS] Caddyfile security headers: Baseline headers present
[PASS] Dockerfile secrets: No hardcoded secrets
[PASS] CI workflow secrets: No hardcoded secrets

Total: 7 passed, 0 failed
```

## Remaining Production Risks

| Risk | Mitigation | Owner |
|---|---|---|
| Production secrets not rotated | Rotate before go-live | Operator |
| SSH password auth enabled | Verify `PasswordAuthentication no` | Operator |
| Firewall not enabled | Enable `ufw` with 22/80/443 only | Operator |
| `APP_ENV` not `production` | Set in production `.env` | Operator |
| `PUBLIC_HOSTNAME` not set | Set to real domain | Operator |

## Governance Correction

The Phase 2D execution plan defines Slice 6 (Real UAT Flow) and Slice 7
(Go-Live Gate). Slice 5 closes the production-hardening readiness work, but it
does not complete Phase 2D and does not authorize go-live.

## Next Gate

Slice 6 (Real UAT Flow) remains approval-gated and must prove real login,
report submission, evidence retrieval, quality gate, approval, publish, and
download with no mocked backend responses. Slice 7 (Go-Live Gate) follows only
after Slice 6 passes. Production remains `NOT_LIVE`.

## Related Documents

- `docs/operations/production_hardening_checklist.md` — Full hardening checklist
- `docs/policies/secrets_policy.md` — Secrets management policy
- `scripts/check_hardening.py` — Automated hardening posture checker
- `docs/execution/PHASE_2D_EXECUTION_PLAN.md` — Original execution plan
- `docs/execution/PHASE_2D_NEXT_STEPS_PLAN.md` — Next steps plan
