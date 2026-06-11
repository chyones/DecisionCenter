# Deployment Overrides (docker-compose.override.yml)

**Status:** mandatory operator step for the current shared-host deployment.
**Template:** [`docker-compose.override.example.yml`](../../docker-compose.override.example.yml)

## Why an override is required

`docker-compose.yml` alone assumes a dedicated host: Caddy publishes host ports
80/443 and MinIO publishes 9000/9001. The current deployment host is shared
with VirtualTour360, whose services already own those ports. A fresh clone
brought up without the override will fail with port conflicts and will have no
external ingress.

The git-ignored `docker-compose.override.yml` therefore:

1. **Remaps MinIO** to `127.0.0.1:9002/9003` (vt360_minio owns 9000/9001).
2. **Removes Caddy host ports** (`ports: !reset []`) — vt360_caddy owns 80/443.
3. **Adds a `cloudflared` service** that runs a DecisionCenter-scoped
   Cloudflare Tunnel routing the public hostname (`vantage.elrace.com`) to
   `http://caddy:80` over the compose network. TLS terminates at the
   Cloudflare edge; no host ports are published.

## Operator setup

```bash
cp docker-compose.override.example.yml docker-compose.override.yml
# Set the tunnel token (git-ignored .env or shell env):
#   CLOUDFLARED_TUNNEL_TOKEN=<token from Cloudflare Zero Trust dashboard>
docker compose up -d
```

## Notes

- The tunnel token is a secret. It lives only in `.env` / shell env — never in
  the override file or any tracked file.
- `cloudflare/cloudflared:latest` is unpinned for convenience; pin a release
  for production go-live.
- On a dedicated production host (no port conflicts), the MinIO/Caddy port
  overrides are unnecessary; keep only the `cloudflared` service if tunnel
  ingress is retained.
