"""Repair live n8n webhook routing + credential binding for the DecisionCenter
SharePoint/email webhooks — without the n8n UI, without re-importing workflows,
and (importantly) without restarting n8n.

Root cause (n8n 1.91.x, verified against the running container)
--------------------------------------------------------------
The ``Receive Request`` webhook node in ``sharepoint_search`` / ``email_search``
was missing its node-level ``webhookId`` (the known-good ``odoo_read`` node has
``webhookId: dc-odoo-read``). In ``NodeHelpers.getNodeWebhookPath`` a node with
``webhookId === undefined`` produces the production path
``<workflowId>/<nodename>/<path>`` instead of ``<path>``. That mismatch:
  * registered a malformed ``webhook_entity`` row (``webhookId=NULL``,
    ``pathLength=NULL``), and
  * at request time made ``LiveWebhooks.executeWebhook`` compute a webhook path
    that did not match the cached row's ``webhookPath`` ("sharepoint-search"),
    so ``getNodeWebhooks(...).find(...)`` returned ``undefined`` and
    ``webhookData.node`` threw HTTP 500 ("Cannot read properties of undefined
    (reading 'node')") *before execution*.

Why no restart is needed
------------------------
``LiveWebhooks.executeWebhook`` loads the workflow nodes FRESH from the DB on
every request (only the ``webhook_entity`` lookup is cached, and that already
returns the correct clean row). Writing the node-level ``webhookId`` to the DB
is therefore picked up on the next webhook call. The webhook node uses
``isFullPath: true``, so with any defined ``webhookId`` the computed path is just
``<path>`` again — matching the cached clean row.

What this script does (target workflows only: sharepoint_search, email_search)
  1. timestamped SQLite backup before any write;
  2. set the ``Receive Request`` node-level ``webhookId`` (reused from the
     existing clean ``webhook_entity`` row, else ``dc-<path>``);
  3. ensure the node has ``authentication=headerAuth`` + ``credentials.httpHeaderAuth``
     bound to the existing credential;
  4. delete malformed/duplicate ``webhook_entity`` rows
     (``pathLength IS NULL`` OR ``webhookId IS NULL`` OR ``webhookPath`` != the
     workflow's production path);
  5. ensure the workflow stays active.

Idempotent and safe to re-run. odoo_read is never modified.

Usage
-----
    python scripts/repair_n8n_webhooks.py            # repair + backup (no restart needed)
    python scripts/repair_n8n_webhooks.py --dry-run  # inspect only, no write
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/var/lib/docker/volumes/decisioncenter_n8n-data/_data/database.sqlite")
CREDENTIAL_ID = "90d9168a-bd77-461f-a4dc-d104210f2f07"
CREDENTIAL_NAME = "DecisionCenter Webhook Header Auth"
CREDENTIAL_TYPE = "httpHeaderAuth"
# (workflow name -> production webhook path) — repaired workflows only.
TARGETS = {
    "sharepoint_search": "sharepoint-search",
    "email_search": "email-search",
}


def _backup(db: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = db.with_name(db.name + f".backup-{ts}")
    shutil.copy2(db, dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="Repair n8n SharePoint/email webhook routing + auth")
    ap.add_argument("--db", default=str(DB_PATH), help="path to n8n database.sqlite")
    ap.add_argument("--dry-run", action="store_true", help="inspect only; no writes")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"ERROR: DB not found at {db}", file=sys.stderr)
        return 1

    if not args.dry_run:
        print(f"Backup: {_backup(db)}")

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        if not con.execute(
            "SELECT 1 FROM credentials_entity WHERE id = ?", (CREDENTIAL_ID,)
        ).fetchone():
            print(f"ERROR: credential {CREDENTIAL_ID} not found", file=sys.stderr)
            return 1

        total_deleted = 0
        for wf_name, prod_path in TARGETS.items():
            wf = con.execute(
                "SELECT id, active, nodes FROM workflow_entity WHERE name = ?", (wf_name,)
            ).fetchone()
            if not wf:
                print(f"  SKIP {wf_name!r}: workflow not found")
                continue
            wf_id = wf["id"]

            rows = con.execute(
                "SELECT webhookPath, webhookId, pathLength FROM webhook_entity WHERE workflowId = ?",
                (wf_id,),
            ).fetchall()
            # canonical webhookId: reuse the existing clean prod-path row's id, else dc-<path>
            canonical = next(
                (r["webhookId"] for r in rows if r["webhookPath"] == prod_path and r["webhookId"]),
                f"dc-{prod_path}",
            )
            malformed = [
                r for r in rows
                if r["pathLength"] is None or r["webhookId"] is None or r["webhookPath"] != prod_path
            ]
            print(f"\n[{wf_name}] id={wf_id} canonical webhookId={canonical}")
            print(f"  rows before: {[(r['webhookPath'][:38], r['webhookId'], r['pathLength']) for r in rows]}")
            print(f"  to remove:   {[r['webhookPath'][:38] for r in malformed]}")

            # node fix: webhookId + auth + credential (idempotent)
            nodes = json.loads(wf["nodes"])
            changed = False
            for node in nodes:
                if node.get("name") != "Receive Request":
                    continue
                if node.get("webhookId") != canonical:
                    node["webhookId"] = canonical
                    changed = True
                params = node.setdefault("parameters", {})
                if params.get("authentication") != "headerAuth":
                    params["authentication"] = "headerAuth"
                    changed = True
                creds = node.get("credentials", {})
                if creds.get(CREDENTIAL_TYPE, {}).get("id") != CREDENTIAL_ID:
                    node["credentials"] = {
                        CREDENTIAL_TYPE: {"id": CREDENTIAL_ID, "name": CREDENTIAL_NAME}
                    }
                    changed = True
                break
            print(f"  node webhookId/auth/cred: {'updated' if changed else 'already ok'}")

            if not args.dry_run:
                if changed or not wf["active"]:
                    con.execute(
                        "UPDATE workflow_entity SET nodes = ?, active = 1 WHERE id = ?",
                        (json.dumps(nodes), wf_id),
                    )
                if malformed:
                    deleted = con.execute(
                        "DELETE FROM webhook_entity WHERE workflowId = ? "
                        "AND (pathLength IS NULL OR webhookId IS NULL OR webhookPath != ?)",
                        (wf_id, prod_path),
                    ).rowcount
                    total_deleted += deleted
                    print(f"  deleted webhook rows: {deleted}")

        if not args.dry_run:
            con.commit()
            print(f"\nCommitted. Total malformed rows deleted: {total_deleted}")

        print("\nVerification (post-repair DB state):")
        for wf_name, prod_path in TARGETS.items():
            wf = con.execute(
                "SELECT id, active, nodes FROM workflow_entity WHERE name = ?", (wf_name,)
            ).fetchone()
            rr = next(n for n in json.loads(wf["nodes"]) if n.get("name") == "Receive Request")
            rows = con.execute(
                "SELECT webhookPath, webhookId, pathLength FROM webhook_entity WHERE workflowId = ?",
                (wf["id"],),
            ).fetchall()
            malformed_left = [r for r in rows if r["pathLength"] is None or r["webhookId"] is None]
            cred = rr.get("credentials", {}).get(CREDENTIAL_TYPE, {}).get("id")
            print(
                f"  {wf_name}: active={bool(wf['active'])} node.webhookId={rr.get('webhookId')} "
                f"cred_bound={cred == CREDENTIAL_ID} rows={[(r['webhookPath'][:24], r['pathLength']) for r in rows]} "
                f"malformed_remaining={len(malformed_left)}"
            )
    finally:
        con.close()

    print("\nNo n8n restart required: workflow nodes are loaded fresh per webhook request.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
