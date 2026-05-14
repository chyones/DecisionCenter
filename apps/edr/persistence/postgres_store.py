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


_postgres_store: PostgresStore | None = None


def get_postgres_store() -> PostgresStore:
    global _postgres_store
    if _postgres_store is None:
        _postgres_store = PostgresStore()
    return _postgres_store
