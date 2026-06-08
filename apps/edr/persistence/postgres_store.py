"""PostgreSQL audit persistence."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg

from apps.edr.config import settings


class PostgresStore:
    """Async PostgreSQL store for audit rows and review decisions."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                min_size=1,
                max_size=5,
            )
        return self._pool

    async def init_schema(self) -> None:
        """Idempotently create the audit_log and review_decisions tables."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    user_id_hash TEXT NOT NULL,
                    project_code TEXT,
                    query TEXT,
                    quality_gate_status TEXT,
                    token_counts JSONB,
                    cost_total_usd NUMERIC(12,6),
                    artifact_keys JSONB,
                    review_state TEXT DEFAULT 'staging',
                    requires_approval BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                ALTER TABLE audit_log
                ADD COLUMN IF NOT EXISTS review_state TEXT DEFAULT 'staging'
                """
            )
            await conn.execute(
                """
                ALTER TABLE audit_log
                ADD COLUMN IF NOT EXISTS requires_approval BOOLEAN DEFAULT TRUE
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_decisions (
                    id SERIAL PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    reviewer_id_hash TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT,
                    comment TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_events (
                    id BIGSERIAL PRIMARY KEY,
                    ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    service TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    latency_ms INTEGER,
                    status_code INTEGER,
                    detail TEXT NOT NULL DEFAULT ''
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS connector_events_service_ts_idx
                    ON connector_events (service, ts DESC)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_events (
                    id BIGSERIAL PRIMARY KEY,
                    ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    event_type TEXT NOT NULL,
                    actor_hash TEXT,
                    project_code TEXT,
                    detail TEXT NOT NULL DEFAULT ''
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS admin_events_ts_idx
                    ON admin_events (ts DESC)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entra_group_mappings (
                    entra_group_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_mappings (
                    project_code     TEXT PRIMARY KEY,
                    project_name     TEXT NOT NULL DEFAULT '',
                    contract_numbers JSONB NOT NULL DEFAULT '[]',
                    sharepoint       JSONB NOT NULL DEFAULT '{}',
                    owncloud         JSONB NOT NULL DEFAULT '{}',
                    email            JSONB NOT NULL DEFAULT '{}',
                    microsoft        JSONB NOT NULL DEFAULT '{}',
                    odoo             JSONB NOT NULL DEFAULT '{}',
                    related_people   JSONB NOT NULL DEFAULT '{}',
                    enabled_sources  JSONB NOT NULL DEFAULT '[]',
                    allowed_roles    JSONB NOT NULL DEFAULT '[]',
                    mapping_status   TEXT NOT NULL DEFAULT 'incomplete',
                    last_validation_result JSONB,
                    last_validated_at      TIMESTAMP WITH TIME ZONE,
                    created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    created_by_hash  TEXT,
                    updated_by_hash  TEXT
                )
                """
            )
            await conn.execute(
                """
                ALTER TABLE source_mappings
                ADD COLUMN IF NOT EXISTS microsoft JSONB NOT NULL DEFAULT '{}'
                """
            )
            await self._seed_source_mappings(conn)
            await self._migrate_project_names(conn)
            await self._migrate_verified_prj_source_mappings(conn)

    async def insert_audit(
        self,
        *,
        request_id: str,
        user_id_hash: str,
        project_code: str | None,
        query: str | None,
        quality_gate_status: str | None,
        token_counts: dict[str, int],
        cost_total_usd: float,
        artifact_keys: list[str],
        review_state: str = "staging",
        requires_approval: bool = True,
    ) -> None:
        """Insert or update an audit row for the given request."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log (
                    request_id, user_id_hash, project_code, query,
                    quality_gate_status, token_counts, cost_total_usd, artifact_keys,
                    review_state, requires_approval
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (request_id) DO UPDATE SET
                    user_id_hash = EXCLUDED.user_id_hash,
                    project_code = EXCLUDED.project_code,
                    query = EXCLUDED.query,
                    quality_gate_status = EXCLUDED.quality_gate_status,
                    token_counts = EXCLUDED.token_counts,
                    cost_total_usd = EXCLUDED.cost_total_usd,
                    artifact_keys = EXCLUDED.artifact_keys,
                    review_state = EXCLUDED.review_state,
                    requires_approval = EXCLUDED.requires_approval,
                    updated_at = NOW()
                """,
                request_id,
                user_id_hash,
                project_code,
                query,
                quality_gate_status,
                json.dumps(token_counts),
                cost_total_usd,
                json.dumps(artifact_keys),
                review_state,
                requires_approval,
            )

    async def get_audit(self, request_id: str) -> dict[str, Any] | None:
        """Fetch an audit row by request_id."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM audit_log WHERE request_id = $1",
                request_id,
            )
            if row is None:
                return None
            return dict(row)

    async def list_audits(
        self,
        *,
        user_id_hash: str | None = None,
        state: str | None = None,
        project_code: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List audit rows filtered by RBAC scope and query params.

        When ``user_id_hash`` is provided, results are scoped to that requester
        (typical for non-auditor roles). When it is ``None``, results span all
        users (auditor scope). The total row count for the filter is returned
        alongside the page so the API can present pagination.

        ``state`` is the *external* state name (``staging``, ``needs_review``,
        ``approved``, ``rejected``, ``revision_requested``, ``final``,
        ``cancelled``, ``failed``). It maps to the underlying ``review_state``
        and ``quality_gate_status`` columns.
        """
        clauses: list[str] = []
        params: list[Any] = []

        def _add(clause: str, value: Any) -> None:
            params.append(value)
            clauses.append(clause.replace("?", f"${len(params)}"))

        if user_id_hash is not None:
            _add("user_id_hash = ?", user_id_hash)
        if project_code is not None:
            _add("project_code = ?", project_code)
        if state is not None:
            if state == "failed":
                _add("quality_gate_status = ?", "failed")
            elif state == "needs_review":
                _add("quality_gate_status = ?", "needs_review")
                _add("review_state = ?", "staging")
            elif state in {
                "approved",
                "rejected",
                "revision_requested",
                "final",
                "cancelled",
            }:
                _add("review_state = ?", state)
            elif state == "staging":
                # External "staging" means: workflow done, awaiting decision, gate not failed
                _add("review_state = ?", "staging")
                _add("quality_gate_status <> ?", "failed")
            else:
                # Unknown state filter — return empty.
                return ([], 0)
        if date_from is not None:
            _add("created_at >= ?", date_from)
        if date_to is not None:
            _add("created_at <= ?", date_to)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                f"SELECT COUNT(*) AS n FROM audit_log {where}",
                *params,
            )
            total = int(count_row["n"]) if count_row else 0

            rows = await conn.fetch(
                f"""
                SELECT *
                FROM audit_log
                {where}
                ORDER BY created_at DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
                """,
                *params,
                limit,
                offset,
            )
            return ([dict(r) for r in rows], total)

    async def update_review_state(
        self, request_id: str, review_state: str
    ) -> None:
        """Update the review_state column for a request."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE audit_log SET review_state = $1, updated_at = NOW() WHERE request_id = $2",
                review_state,
                request_id,
            )

    async def insert_review_decision(
        self,
        *,
        request_id: str,
        reviewer_id_hash: str,
        action: str,
        reason: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Insert a review decision record."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO review_decisions (
                    request_id, reviewer_id_hash, action, reason, comment
                ) VALUES ($1, $2, $3, $4, $5)
                """,
                request_id,
                reviewer_id_hash,
                action,
                reason,
                comment,
            )

    async def get_review_decisions(self, request_id: str) -> list[dict[str, Any]]:
        """Fetch all review decisions for a request, newest first."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM review_decisions
                WHERE request_id = $1
                ORDER BY created_at DESC
                """,
                request_id,
            )
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Phase 2B Slice 2 — connector events
    # ------------------------------------------------------------------

    async def insert_connector_event(
        self,
        *,
        service: str,
        event_type: str,
        latency_ms: int | None,
        status_code: int | None,
        detail: str,
    ) -> int:
        """Insert a connector probe / latency-spike row and return its id.

        ``detail`` is expected to be pre-sanitised by the caller
        (``apps.edr.admin.services_catalog._sanitize_detail``); this method
        does not redact further.
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO connector_events (
                    service, event_type, latency_ms, status_code, detail
                ) VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                service,
                event_type,
                latency_ms,
                status_code,
                detail,
            )
            return int(row["id"]) if row else 0

    async def latest_connector_event_per_service(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Return the newest row per service keyed by service name."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (service)
                    service, ts, event_type, latency_ms, status_code, detail
                FROM connector_events
                ORDER BY service, ts DESC
                """
            )
            return {r["service"]: dict(r) for r in rows}

    async def recent_connector_events(
        self, service: str, *, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return up to ``limit`` most recent rows for one service."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ts, event_type, latency_ms, status_code, detail
                FROM connector_events
                WHERE service = $1
                ORDER BY ts DESC
                LIMIT $2
                """,
                service,
                limit,
            )
            return [dict(r) for r in rows]

    async def connector_events_24h_buckets(
        self, service: str
    ) -> list[dict[str, Any]]:
        """Return 24 hourly latency averages for the service (last 24h)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    date_trunc('hour', ts) AS bucket,
                    COALESCE(AVG(latency_ms), 0)::int AS avg_latency_ms
                FROM connector_events
                WHERE service = $1
                  AND ts >= NOW() - INTERVAL '24 hours'
                  AND latency_ms IS NOT NULL
                GROUP BY date_trunc('hour', ts)
                ORDER BY bucket ASC
                """,
                service,
            )
            return [dict(r) for r in rows]

    async def monthly_cost_aggregate(self) -> float:
        """Return the sum of cost_total_usd for the current calendar month."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COALESCE(SUM(cost_total_usd), 0)::float AS total
                FROM audit_log
                WHERE created_at >= date_trunc('month', NOW())
                """
            )
            return float(row["total"]) if row else 0.0

    async def monthly_llm_call_count(self) -> int:
        """Return the count of audit_log rows for the current calendar month."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS n
                FROM audit_log
                WHERE created_at >= date_trunc('month', NOW())
                """
            )
            return int(row["n"]) if row else 0

    async def insert_cost_event(self, event_type: str, detail: str) -> int:
        """Insert a cost warning or cap-exceeded event into connector_events.

        Uses ``service='cost'`` so the Slice 4 audit read-model can filter
        cost events uniformly.
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO connector_events (service, event_type, detail)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "cost",
                event_type,
                detail,
            )
            return int(row["id"]) if row else 0

    # ------------------------------------------------------------------
    # Phase 2B Slice 4 — Audit Log read-model + admin_events writer
    # ------------------------------------------------------------------

    async def list_audit_events(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a paginated, filtered UNION over all event tables.

        Composite ``event_id`` prefixes prevent cross-table collisions:
        ``al:`` = audit_log, ``rd:`` = review_decisions,
        ``ce:`` = connector_events, ``ae:`` = admin_events.
        No query text, report content, or evidence excerpts are selected (C-1).
        """
        clauses: list[str] = []
        params: list[Any] = []

        def _add(clause: str, value: Any) -> None:
            params.append(value)
            clauses.append(clause.replace("?", f"${len(params)}"))

        if date_from is not None:
            _add("ts >= ?", date_from)
        if date_to is not None:
            _add("ts <= ?", date_to)
        if event_type is not None:
            _add("event_type = ?", event_type)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                f"""
                WITH unified AS (
                    SELECT
                        'al:' || id AS event_id,
                        created_at AS ts,
                        'report.submitted' AS event_type,
                        user_id_hash,
                        project_code,
                        NULL::text AS service,
                        'state=' || COALESCE(review_state, 'unknown')
                        || ' qg=' || COALESCE(quality_gate_status, 'unknown') AS detail
                    FROM audit_log
                    UNION ALL
                    SELECT
                        'rd:' || id,
                        created_at,
                        action,
                        reviewer_id_hash,
                        NULL,
                        NULL,
                        COALESCE(reason, '') || COALESCE(
                            CASE WHEN comment IS NOT NULL AND comment <> ''
                                 THEN ' | ' || comment ELSE '' END, ''
                        )
                    FROM review_decisions
                    UNION ALL
                    SELECT
                        'ce:' || id,
                        ts,
                        event_type,
                        NULL,
                        NULL,
                        service,
                        detail
                    FROM connector_events
                    UNION ALL
                    SELECT
                        'ae:' || id,
                        ts,
                        event_type,
                        actor_hash,
                        project_code,
                        NULL,
                        detail
                    FROM admin_events
                )
                SELECT COUNT(*) AS n FROM unified {where}
                """,
                *params,
            )
            total = int(count_row["n"]) if count_row else 0

            rows = await conn.fetch(
                f"""
                WITH unified AS (
                    SELECT
                        'al:' || id AS event_id,
                        created_at AS ts,
                        'report.submitted' AS event_type,
                        user_id_hash,
                        project_code,
                        NULL::text AS service,
                        'state=' || COALESCE(review_state, 'unknown')
                        || ' qg=' || COALESCE(quality_gate_status, 'unknown') AS detail
                    FROM audit_log
                    UNION ALL
                    SELECT
                        'rd:' || id,
                        created_at,
                        action,
                        reviewer_id_hash,
                        NULL,
                        NULL,
                        COALESCE(reason, '') || COALESCE(
                            CASE WHEN comment IS NOT NULL AND comment <> ''
                                 THEN ' | ' || comment ELSE '' END, ''
                        )
                    FROM review_decisions
                    UNION ALL
                    SELECT
                        'ce:' || id,
                        ts,
                        event_type,
                        NULL,
                        NULL,
                        service,
                        detail
                    FROM connector_events
                    UNION ALL
                    SELECT
                        'ae:' || id,
                        ts,
                        event_type,
                        actor_hash,
                        project_code,
                        NULL,
                        detail
                    FROM admin_events
                )
                SELECT * FROM unified {where}
                ORDER BY ts DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
                """,
                *params,
                limit,
                offset,
            )
            return ([dict(r) for r in rows], total)

    async def get_audit_event(self, event_id: str) -> dict[str, Any] | None:
        """Fetch a single unified event by its composite id."""
        if ":" not in event_id:
            return None
        prefix, raw_id = event_id.split(":", 1)
        try:
            pk = int(raw_id)
        except ValueError:
            return None

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if prefix == "al":
                row = await conn.fetchrow(
                    """
                    SELECT
                        'al:' || id AS event_id,
                        created_at AS ts,
                        'report.submitted' AS event_type,
                        user_id_hash,
                        project_code,
                        NULL::text AS service,
                        'state=' || COALESCE(review_state, 'unknown')
                        || ' qg=' || COALESCE(quality_gate_status, 'unknown') AS detail
                    FROM audit_log WHERE id = $1
                    """,
                    pk,
                )
            elif prefix == "rd":
                row = await conn.fetchrow(
                    """
                    SELECT
                        'rd:' || id AS event_id,
                        created_at AS ts,
                        action AS event_type,
                        reviewer_id_hash AS user_id_hash,
                        NULL AS project_code,
                        NULL::text AS service,
                        COALESCE(reason, '') || COALESCE(
                            CASE WHEN comment IS NOT NULL AND comment <> ''
                                 THEN ' | ' || comment ELSE '' END, ''
                        ) AS detail
                    FROM review_decisions WHERE id = $1
                    """,
                    pk,
                )
            elif prefix == "ce":
                row = await conn.fetchrow(
                    """
                    SELECT
                        'ce:' || id AS event_id,
                        ts,
                        event_type,
                        NULL AS user_id_hash,
                        NULL AS project_code,
                        service,
                        detail
                    FROM connector_events WHERE id = $1
                    """,
                    pk,
                )
            elif prefix == "ae":
                row = await conn.fetchrow(
                    """
                    SELECT
                        'ae:' || id AS event_id,
                        ts,
                        event_type,
                        actor_hash AS user_id_hash,
                        project_code,
                        NULL::text AS service,
                        detail
                    FROM admin_events WHERE id = $1
                    """,
                    pk,
                )
            else:
                return None
            return dict(row) if row else None

    async def list_entra_mappings(self) -> list[dict[str, Any]]:
        """Return all Entra group mappings ordered by created_at ASC."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entra_group_id, role, created_at, updated_at
                FROM entra_group_mappings
                ORDER BY created_at ASC
                """
            )
            return [dict(r) for r in rows]

    async def upsert_entra_mapping(
        self,
        *,
        entra_group_id: str,
        role: str,
    ) -> None:
        """Insert or update an Entra group → role mapping."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO entra_group_mappings (entra_group_id, role)
                VALUES ($1, $2)
                ON CONFLICT (entra_group_id)
                DO UPDATE SET role = EXCLUDED.role, updated_at = NOW()
                """,
                entra_group_id,
                role,
            )

    async def delete_entra_mapping(self, entra_group_id: str) -> bool:
        """Delete an Entra group mapping. Returns True if a row was removed."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            status: str = await conn.execute(
                "DELETE FROM entra_group_mappings WHERE entra_group_id = $1",
                entra_group_id,
            )
            return status == "DELETE 1"

    async def get_entra_mapping(self, entra_group_id: str) -> dict[str, Any] | None:
        """Fetch a single mapping by group id, or None if absent."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT entra_group_id, role, created_at, updated_at
                FROM entra_group_mappings
                WHERE entra_group_id = $1
                """,
                entra_group_id,
            )
            return dict(row) if row else None

    async def _seed_source_mappings(self, conn: Any) -> None:
        """Seed source_mappings from project_source_mapping.json if table is empty."""
        import json as _json
        from pathlib import Path

        count = await conn.fetchval("SELECT COUNT(*) FROM source_mappings")
        if count != 0:
            return
        json_path = Path(__file__).parents[3] / "docs" / "config" / "project_source_mapping.json"
        if not json_path.exists():
            return
        with open(json_path, encoding="utf-8") as f:
            entries = _json.load(f)
        for entry in entries:
            code = entry["project_code"]
            sp = entry.get("sharepoint", {})
            oc = entry.get("owncloud", {})
            em = entry.get("email", {})
            ms = entry.get("microsoft", {})
            od = entry.get("odoo", {})
            rp = entry.get("related_people", {})
            enabled_sources = entry.get(
                "enabled_sources", ["sharepoint", "owncloud", "email", "odoo"]
            )
            await conn.execute(
                """
                INSERT INTO source_mappings
                    (project_code, project_name, contract_numbers, sharepoint, owncloud,
                     email, microsoft, odoo, related_people, enabled_sources, mapping_status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (project_code) DO NOTHING
                """,
                code,
                entry.get("project_name") or entry.get("display_name") or code,
                _json.dumps(entry.get("contract_numbers", [])),
                _json.dumps({
                    "site_id": sp.get("site_id", ""),
                    "drive_id": sp.get("drive_id", ""),
                    "root_path": sp.get("root_path", ""),
                }),
                _json.dumps({"base_path": oc.get("base_path", "")}),
                _json.dumps({
                    "shared_mailboxes": em.get("shared_mailboxes", []),
                    "document_control_mailbox": em.get("document_control_mailbox", ""),
                    "client_domains": [],
                    "consultant_domains": [],
                    "contractor_domains": [],
                }),
                _json.dumps({
                    "group": ms.get("group", {}),
                    "group_members": ms.get("group_members", []),
                    "group_membership_status": ms.get("group_membership_status", ""),
                    "member_count": ms.get("member_count", len(ms.get("group_members", []))),
                    "missing_permissions": ms.get("missing_permissions", []),
                    "blockers": ms.get("blockers", []),
                }),
                _json.dumps({
                    "project_model": od.get("project_model", ""),
                    "cost_model": od.get("cost_model", ""),
                    "project_external_id": od.get("project_external_id", ""),
                    "project_name": od.get("project_name", ""),
                    "analytic_account_id": str(od.get("analytic_account_id", "")),
                }),
                _json.dumps({
                    "project_manager": rp.get("project_manager", ""),
                    "commercial_manager": rp.get("commercial_manager", ""),
                    "finance_owner": rp.get("finance_owner", ""),
                    "document_controller": rp.get("document_controller", ""),
                    "other": rp.get("other", []),
                }),
                _json.dumps(enabled_sources),
                entry.get("mapping_status") or "complete",
            )

    async def _migrate_project_names(self, conn: Any) -> None:
        """Back-fill project_name for rows that still have an empty name (idempotent)."""
        import json as _json
        from pathlib import Path

        json_path = Path(__file__).parents[3] / "docs" / "config" / "project_source_mapping.json"
        if not json_path.exists():
            return
        with open(json_path, encoding="utf-8") as f:
            entries = _json.load(f)
        for entry in entries:
            code = entry["project_code"]
            name = entry.get("display_name") or ""
            if not name:
                continue
            await conn.execute(
                """
                UPDATE source_mappings
                SET project_name = $2
                WHERE project_code = $1 AND project_name = ''
                """,
                code,
                name,
            )

    async def _migrate_verified_prj_source_mappings(self, conn: Any) -> None:
        """Idempotently repair the two verified PRJ source mappings.

        These internal PRJ rows were seeded before the real Odoo names, Odoo
        ids, and SharePoint ids were verified. Keep the rows, but replace the
        placeholder source coordinates with the verified Odoo + SharePoint
        truth from docs/config/project_source_mapping.json.

        Columns that hold enriched Microsoft Graph data (microsoft,
        related_people, enabled_sources, mapping_status,
        last_validation_result) are preserved when the row already has a real
        group_membership_status from a completed enrichment run so that a
        Docker restart does not wipe live data.
        """
        import json as _json
        from pathlib import Path

        json_path = Path(__file__).parents[3] / "docs" / "config" / "project_source_mapping.json"
        if not json_path.exists():
            return
        with open(json_path, encoding="utf-8") as f:
            entries = _json.load(f)

        for entry in entries:
            code = entry.get("project_code")
            if code not in {"PRJ-001", "PRJ-002"}:
                continue

            sp = entry.get("sharepoint", {})
            oc = entry.get("owncloud", {})
            em = entry.get("email", {})
            ms = entry.get("microsoft", {})
            od = entry.get("odoo", {})
            rp = entry.get("related_people", {})
            enabled_sources = entry.get("enabled_sources", ["sharepoint", "odoo"])
            project_name = entry.get("project_name") or entry.get("display_name") or ""

            await conn.execute(
                """
                UPDATE source_mappings
                SET project_name = $2,
                    contract_numbers = $3,
                    sharepoint = $4,
                    owncloud = $5,
                    email = $6,
                    microsoft = CASE
                        WHEN COALESCE(microsoft->>'group_membership_status','') = ANY(
                            ARRAY['GROUP_MEMBERS_READ','GROUP_FOUND_NO_MEMBERS','GROUP_FOUND_NO_MAILBOX']
                        ) THEN microsoft
                        ELSE $7::jsonb
                    END,
                    odoo = $8,
                    related_people = CASE
                        WHEN COALESCE(microsoft->>'group_membership_status','') = ANY(
                            ARRAY['GROUP_MEMBERS_READ','GROUP_FOUND_NO_MEMBERS','GROUP_FOUND_NO_MAILBOX']
                        ) THEN related_people
                        ELSE $9::jsonb
                    END,
                    enabled_sources = CASE
                        WHEN COALESCE(microsoft->>'group_membership_status','') = ANY(
                            ARRAY['GROUP_MEMBERS_READ','GROUP_FOUND_NO_MEMBERS','GROUP_FOUND_NO_MAILBOX']
                        ) THEN enabled_sources
                        ELSE $10::jsonb
                    END,
                    mapping_status = CASE
                        WHEN COALESCE(microsoft->>'group_membership_status','') = ANY(
                            ARRAY['GROUP_MEMBERS_READ','GROUP_FOUND_NO_MEMBERS','GROUP_FOUND_NO_MAILBOX']
                        ) THEN mapping_status
                        ELSE $11
                    END,
                    last_validation_result = CASE
                        WHEN COALESCE(microsoft->>'group_membership_status','') = ANY(
                            ARRAY['GROUP_MEMBERS_READ','GROUP_FOUND_NO_MEMBERS','GROUP_FOUND_NO_MAILBOX']
                        ) THEN last_validation_result
                        ELSE $12::jsonb
                    END,
                    last_validated_at = NOW(),
                    updated_at = NOW()
                WHERE project_code = $1
                """,
                code,
                project_name,
                _json.dumps(entry.get("contract_numbers", [])),
                _json.dumps({
                    "site_id": sp.get("site_id", ""),
                    "drive_id": sp.get("drive_id", ""),
                    "root_path": sp.get("root_path", ""),
                }),
                _json.dumps({"base_path": oc.get("base_path", "")}),
                _json.dumps({
                    "shared_mailboxes": em.get("shared_mailboxes", []),
                    "document_control_mailbox": em.get("document_control_mailbox", ""),
                    "client_domains": em.get("client_domains", []),
                    "consultant_domains": em.get("consultant_domains", []),
                    "contractor_domains": em.get("contractor_domains", []),
                }),
                _json.dumps({
                    "group": ms.get("group", {}),
                    "group_members": ms.get("group_members", []),
                    "group_membership_status": ms.get("group_membership_status", ""),
                    "member_count": ms.get("member_count", len(ms.get("group_members", []))),
                    "missing_permissions": ms.get("missing_permissions", []),
                    "blockers": ms.get("blockers", []),
                }),
                _json.dumps({
                    "project_model": od.get("project_model", ""),
                    "cost_model": od.get("cost_model", ""),
                    "project_external_id": od.get("project_external_id", ""),
                    "project_name": od.get("project_name", ""),
                    "analytic_account_id": str(od.get("analytic_account_id", "")),
                }),
                _json.dumps({
                    "project_manager": rp.get("project_manager", ""),
                    "commercial_manager": rp.get("commercial_manager", ""),
                    "finance_owner": rp.get("finance_owner", ""),
                    "document_controller": rp.get("document_controller", ""),
                    "other": rp.get("other", []),
                }),
                _json.dumps(enabled_sources),
                entry.get("mapping_status") or "complete",
                _json.dumps({"status": entry.get("mapping_status") or "complete", "errors": []}),
            )

    async def list_source_mappings(self) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM source_mappings ORDER BY project_code ASC
                """
            )
            return [dict(r) for r in rows]

    async def list_source_mappings_full(self) -> list[dict[str, Any]]:
        """Return all columns for all source_mappings rows (used by sync engine)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM source_mappings ORDER BY project_code ASC"
            )
            return [dict(r) for r in rows]

    async def get_source_mapping(self, project_code: str) -> dict[str, Any] | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM source_mappings WHERE project_code = $1", project_code
            )
            return dict(row) if row else None

    async def upsert_source_mapping(
        self,
        *,
        project_code: str,
        project_name: str,
        contract_numbers: list,
        sharepoint: dict,
        owncloud: dict,
        email: dict,
        microsoft: dict,
        odoo: dict,
        related_people: dict,
        enabled_sources: list,
        allowed_roles: list,
        mapping_status: str,
        actor_hash: str | None,
    ) -> None:
        import json as _json

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO source_mappings
                    (project_code, project_name, contract_numbers, sharepoint,
                     owncloud, email, microsoft, odoo, related_people, enabled_sources,
                     allowed_roles, mapping_status, updated_at, updated_by_hash,
                     created_by_hash)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,NOW(),$13,$13)
                ON CONFLICT (project_code) DO UPDATE SET
                    project_name     = EXCLUDED.project_name,
                    contract_numbers = EXCLUDED.contract_numbers,
                    sharepoint       = EXCLUDED.sharepoint,
                    owncloud         = EXCLUDED.owncloud,
                    email            = EXCLUDED.email,
                    microsoft        = EXCLUDED.microsoft,
                    odoo             = EXCLUDED.odoo,
                    related_people   = EXCLUDED.related_people,
                    enabled_sources  = EXCLUDED.enabled_sources,
                    allowed_roles    = EXCLUDED.allowed_roles,
                    mapping_status   = EXCLUDED.mapping_status,
                    updated_at       = NOW(),
                    updated_by_hash  = EXCLUDED.updated_by_hash
                """,
                project_code,
                project_name,
                _json.dumps(contract_numbers),
                _json.dumps(sharepoint),
                _json.dumps(owncloud),
                _json.dumps(email),
                _json.dumps(microsoft or {}),
                _json.dumps(odoo),
                _json.dumps(related_people),
                _json.dumps(enabled_sources),
                _json.dumps(allowed_roles),
                mapping_status,
                actor_hash,
            )

    async def disable_source_mapping(self, project_code: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE source_mappings
                SET mapping_status = 'disabled', updated_at = NOW()
                WHERE project_code = $1
                """,
                project_code,
            )

    async def update_source_mapping_validation(
        self,
        project_code: str,
        status: str,
        result: dict,
    ) -> None:
        import json as _json

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE source_mappings
                SET mapping_status = $2,
                    last_validation_result = $3,
                    last_validated_at = NOW()
                WHERE project_code = $1
                """,
                project_code,
                status,
                _json.dumps(result),
            )

    async def list_approval_queue(
        self,
        *,
        project_code: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List reports pending admin approval.

        Filters: review_state='staging' AND quality_gate_status != 'failed'.
        This covers both external 'staging' and 'needs_review' states (A-09).
        """
        base_clauses = [
            "review_state = 'staging'",
            "COALESCE(quality_gate_status, '') != 'failed'",
        ]
        extra_params: list[Any] = []

        def _add(clause: str, value: Any) -> None:
            extra_params.append(value)
            base_clauses.append(clause.replace("?", f"${len(extra_params)}"))

        if project_code is not None:
            _add("project_code = ?", project_code)

        where = "WHERE " + " AND ".join(base_clauses)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            count_row = await conn.fetchrow(
                f"SELECT COUNT(*) AS n FROM audit_log {where}", *extra_params
            )
            total = int(count_row["n"]) if count_row else 0
            rows = await conn.fetch(
                f"""
                SELECT * FROM audit_log {where}
                ORDER BY created_at DESC
                LIMIT ${len(extra_params) + 1} OFFSET ${len(extra_params) + 2}
                """,
                *extra_params,
                limit,
                offset,
            )
            return ([dict(r) for r in rows], total)

    async def dashboard_counts_today(self) -> dict[str, int]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) AS requests_today,
                    COUNT(*) FILTER (
                        WHERE quality_gate_status = 'failed'
                    ) AS failed_qg_today
                FROM audit_log
                WHERE date_trunc('day', created_at AT TIME ZONE 'UTC')
                    = date_trunc('day', NOW() AT TIME ZONE 'UTC')
                """
            )
            if row is None:
                return {"requests_today": 0, "failed_qg_today": 0}
            return {
                "requests_today": int(row["requests_today"]),
                "failed_qg_today": int(row["failed_qg_today"]),
            }

    async def insert_admin_event(
        self,
        *,
        event_type: str,
        actor_hash: str | None,
        project_code: str | None,
        detail: str,
    ) -> int:
        """Insert an admin event (used by Slices 5–7)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO admin_events (event_type, actor_hash, project_code, detail)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                event_type,
                actor_hash,
                project_code,
                detail,
            )
            return int(row["id"]) if row else 0


_postgres_store: PostgresStore | None = None


def get_postgres_store() -> PostgresStore:
    global _postgres_store
    if _postgres_store is None:
        _postgres_store = PostgresStore()
    return _postgres_store
