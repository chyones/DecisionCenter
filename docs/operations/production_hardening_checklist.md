# Production Hardening Checklist

## Scope

This checklist covers server hardening, secret management, service exposure,
TLS/domain readiness, and SSH security for the DecisionCenter stack running on
Hetzner Cloud (CCX23).  It is the operator-run evidence required for Slice 5.

## Secrets Management

| # | Check | Status | Evidence |
|---|---|---|---|
| S1 | `.env` is never committed to git | ✅ | `.gitignore` excludes `.env` and `.env.*`; `git ls-files` returns no matches |
| S2 | `.env.example` contains only placeholders | ✅ | All sensitive values use `"change-me"` or empty strings; no real API keys |
| S3 | Production secrets are managed outside git | 🔴 | Operator must store production `.env` in the approved secrets manager |
| S4 | LLM provider keys (Anthropic, Voyage, Cohere) are rotated before go-live | 🔴 | Operator action required |
| S5 | MinIO root credentials are rotated before go-live | 🔴 | Operator action required |
| S6 | PostgreSQL password is rotated before go-live | 🔴 | Operator action required |
| S7 | n8n webhook token is rotated before go-live | 🔴 | Operator action required |
| S8 | Entra client secret is rotated before go-live | 🔴 | Operator action required |

## Environment Variable Readiness

| # | Check | Status | Evidence |
|---|---|---|---|
| E1 | `.env.example` covers all 40 config keys | ✅ | CI `Config coverage` step enforces 40/40 |
| E2 | Every key in `.env.example` is loaded by `apps.edr.config.settings` | ✅ | CI enforces this via `set(env_keys) == set(config_keys)` |
| E3 | Production `.env` is complete (no empty required values) | 🔴 | Operator must verify before `make up` |
| E4 | `APP_ENV=production` is set for production | 🔴 | Operator must set in production `.env` |
| E5 | `PUBLIC_HOSTNAME` is set to the real domain | 🔴 | Operator must set (e.g. `decisioncenter.elrace.com`) |

## TLS and Domain Readiness

| # | Check | Status | Evidence |
|---|---|---|---|
| T1 | Caddy serves the configured `PUBLIC_HOSTNAME` | ✅ | `Caddyfile` uses `{$PUBLIC_HOSTNAME:localhost}` |
| T2 | ACME auto-TLS is enabled via Caddy | ✅ | Caddy requests certs automatically when `PUBLIC_HOSTNAME` is a real domain |
| T3 | HSTS header is present | ✅ | `Caddyfile` sets `Strict-Transport-Security max-age=31536000; includeSubDomains` |
| T4 | `X-Content-Type-Options: nosniff` is present | ✅ | `Caddyfile` |
| T5 | `X-Frame-Options: DENY` is present | ✅ | `Caddyfile` |
| T6 | `Referrer-Policy: no-referrer` is present | ✅ | `Caddyfile` |
| T7 | Backend receives `X-Forwarded-Proto` | ✅ | `Caddyfile` proxy headers include `X-Forwarded-Proto {scheme}` |
| T8 | Plain-HTTP fallback (`:80`) exists for healthchecks | ✅ | `Caddyfile` second block |

## Service Exposure Review

### Docker Compose Port Bindings

| Service | Host Binding | Container Port | Exposure | Verdict |
|---|---|---|---|---|
| `app` | `127.0.0.1:8000` | `8000` | localhost only | ✅ Safe |
| `postgres` | *none* | `5432` | internal bridge only | ✅ Safe |
| `redis` | *none* | `6379` | internal bridge only | ✅ Safe |
| `qdrant` | *none* | `6333` | internal bridge only | ✅ Safe |
| `minio` | `127.0.0.1:9000` | `9000` | localhost only | ✅ Safe |
| `minio` | `127.0.0.1:9001` | `9001` | localhost only (console) | ✅ Safe |
| `n8n` | *none* | `5678` | internal bridge only | ✅ Safe |
| `caddy` | `80:80` | `80` | public (HTTP) | ✅ Intended |
| `caddy` | `443:443` | `443` | public (HTTPS) | ✅ Intended |

**Finding:** No internal service is bound to `0.0.0.0` or a public interface.
MinIO API and console are restricted to `127.0.0.1` on the host; operators
who need the console can SSH-tunnel to `127.0.0.1:9001`.

### n8n Editor Access

| # | Check | Status | Evidence |
|---|---|---|---|
| N1 | n8n editor is NOT exposed publicly | ✅ | `docker-compose.yml` uses `expose: 5678` (no host port) |
| N2 | n8n webhooks are reachable from the app container | ✅ | App connects via `http://n8n:5678` inside the compose network |

## SSH Hardening Checklist

Operator must verify on the Hetzner host before go-live:

| # | Check | Status | Evidence |
|---|---|---|---|
| H1 | `PasswordAuthentication no` in `/etc/ssh/sshd_config` | 🔴 | Operator must verify |
| H2 | Root login is disabled (`PermitRootLogin no`) | 🔴 | Operator must verify |
| H3 | Only SSH key auth is allowed | 🔴 | Operator must verify |
| H4 | `fail2ban` is installed and running | 🔴 | Operator must verify |
| H5 | SSH listens on default port 22 (or a non-standard port if desired) | 🔴 | Operator must verify |

## Firewall Rules

Operator must verify on the Hetzner host before go-live:

| # | Check | Status | Evidence |
|---|---|---|---|
| F1 | `ufw` is installed and enabled | 🔴 | Operator must verify |
| F2 | Default incoming policy is `deny` | 🔴 | Operator must verify |
| F3 | Port 22/tcp (SSH) is allowed | 🔴 | Operator must verify |
| F4 | Port 80/tcp (HTTP) is allowed | 🔴 | Operator must verify |
| F5 | Port 443/tcp (HTTPS) is allowed | 🔴 | Operator must verify |
| F6 | No other inbound ports are open | 🔴 | Operator must verify |
| F7 | Outgoing traffic is allowed (default `allow`) | 🔴 | Operator must verify |

## Container Security

| # | Check | Status | Evidence |
|---|---|---|---|
| C1 | App container does not run as root (where feasible) | 🟡 | Current `Dockerfile` uses default root; operator may add `USER` if desired |
| C2 | Image is rebuilt with latest base image patches | 🔴 | Operator must run `docker build --pull` before go-live |
| C3 | No secrets baked into the image | ✅ | `Dockerfile` copies only `pyproject.toml`, `README.md`, `.env.example` |
| C4 | `pip-audit` runs in CI (advisory only) | ✅ | `.github/workflows/ci.yml` step |

## Automated Checks

Run the local hardening checker:

```bash
python3 scripts/check_hardening.py
```

Expected output (all PASS):

```
[PASS] .env.example placeholders: No real secrets detected
[PASS] .gitignore coverage: All required patterns present
[PASS] No committed .env files: No .env files in git index
[PASS] Internal service exposure: Only Caddy is publicly bound
[PASS] Caddyfile security headers: Baseline headers present
[PASS] Dockerfile secrets: No hardcoded secrets
[PASS] CI workflow secrets: No hardcoded secrets
```

JSON output (for operator automation):

```bash
python3 scripts/check_hardening.py --json
```

## Remaining Risks Before Go-Live

| Risk | Mitigation | Owner |
|---|---|---|
| Production secrets not rotated | Rotate all API keys, DB password, MinIO creds before first deploy | Operator |
| SSH not key-only | Verify `PasswordAuthentication no` on Hetzner host | Operator |
| Firewall not enabled | Enable `ufw` and restrict to 22/80/443 | Operator |
| Container runs as root | Optional: add non-root `USER` to Dockerfile | Operator |
| `APP_ENV` not set to `production` | Set in production `.env` | Operator |
| `PUBLIC_HOSTNAME` not set | Set to real domain in production `.env` | Operator |

## Go / No-Go for Production

Production may **not** be declared live until:

1. ✅ Secrets are out of git and managed by a secrets manager.
2. ✅ Internal services are not publicly exposed (verified by `check_hardening.py`).
3. 🔴 All production secrets are rotated (operator action).
4. 🔴 SSH is key-only and `fail2ban` is active (operator action).
5. 🔴 `ufw` is enabled with only 22/80/443 inbound (operator action).
6. 🔴 `APP_ENV=production` and `PUBLIC_HOSTNAME` are set (operator action).

## Related Documents

- `docs/policies/secrets_policy.md` — Secrets management policy
- `docs/operations/hosting.md` — Deployment target (Hetzner CCX23)
- `docs/operations/runbook.md` — Bring-up commands
- `scripts/check_hardening.py` — Automated hardening checks
- `docker-compose.yml` — Service orchestration and port bindings
- `Caddyfile` — TLS, headers, and reverse proxy configuration
