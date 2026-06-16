"""Safe in-place deploy of the updated ``odoo_read`` n8n workflow.

Replaces ONLY the ``Odoo Query`` Code node's ``jsCode`` in the running n8n
SQLite database with the version committed in ``n8n/odoo_read.json`` (structured
``f_*`` evidence fields). The ``Receive Request`` webhook node — including its
``httpHeaderAuth`` credential binding — is never touched, so this avoids the
credential-stripping that a raw ``import:workflow`` causes.

Safe to re-run (idempotent). Backs up the current node JSON before writing.
After running, restart n8n so it reloads the workflow:

    docker compose restart n8n

Requires host access to the ``decisioncenter_n8n-data`` Docker volume.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/var/lib/docker/volumes/decisioncenter_n8n-data/_data/database.sqlite")
REPO_WORKFLOW = Path(__file__).resolve().parents[1] / "n8n" / "odoo_read.json"
BACKUP_DIR = Path(__file__).resolve().parents[1] / "logs"
WORKFLOW_NAME = "odoo_read"
CODE_NODE_NAME = "Odoo Query"
WEBHOOK_NODE_NAME = "Receive Request"


def _load_target_jscode() -> str:
    wf = json.loads(REPO_WORKFLOW.read_text(encoding="utf-8"))
    for node in wf["nodes"]:
        if node.get("name") == CODE_NODE_NAME:
            code = node["parameters"]["jsCode"]
            if not isinstance(code, str) or not code.strip():
                raise SystemExit("ERROR: repo jsCode is empty.")
            return code
    raise SystemExit(f"ERROR: {CODE_NODE_NAME!r} not found in {REPO_WORKFLOW}.")


def _syntax_check(jscode: str) -> None:
    """Validate the jsCode parses (incl. await) by wrapping it in an async fn."""
    wrapped = "async function __n8n_odoo_query__() {\n" + jscode + "\n}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as fh:
        fh.write(wrapped)
        tmp = fh.name
    try:
        res = subprocess.run(
            ["node", "--check", tmp], capture_output=True, text=True
        )
    except FileNotFoundError:
        print("WARN: node not available; skipping syntax check.", file=sys.stderr)
        return
    if res.returncode != 0:
        raise SystemExit(f"ERROR: jsCode failed node --check:\n{res.stderr}")
    print("Syntax check (node --check): OK")


def main() -> int:
    import sqlite3

    if not DB_PATH.exists():
        print(f"ERROR: n8n DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    target = _load_target_jscode()
    _syntax_check(target)

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT id, name, nodes, active FROM workflow_entity WHERE name = ?",
            (WORKFLOW_NAME,),
        ).fetchone()
        if not row:
            print(f"ERROR: workflow {WORKFLOW_NAME!r} not found in n8n DB.", file=sys.stderr)
            return 1

        wf_id = row["id"]
        nodes = json.loads(row["nodes"])
        print(f"Workflow found: name={WORKFLOW_NAME!r} id={wf_id!r} active={row['active']!r}")

        code_node = next((n for n in nodes if n.get("name") == CODE_NODE_NAME), None)
        webhook_node = next((n for n in nodes if n.get("name") == WEBHOOK_NODE_NAME), None)
        if code_node is None:
            print(f"ERROR: {CODE_NODE_NAME!r} node missing in DB workflow.", file=sys.stderr)
            return 1

        # Record the webhook auth BEFORE the change so we can prove it is preserved.
        pre_auth = None
        if webhook_node is not None:
            pre_auth = {
                "authentication": webhook_node.get("parameters", {}).get("authentication"),
                "credentials": webhook_node.get("credentials", {}),
            }

        current = code_node.get("parameters", {}).get("jsCode", "")
        if current == target:
            print("Already up to date — jsCode matches repo. No write performed.")
            structured = "f_' +" in target or "flattenRecord" in target
            print(f"Structured f_* fields present in deployed code: {structured}")
            return 0

        # Backup current nodes JSON before writing.
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"odoo_read_nodes_backup_{ts}.json"
        backup.write_text(json.dumps(nodes, indent=2), encoding="utf-8")
        print(f"Backup written: {backup}")

        # Patch ONLY the code node's jsCode. Nothing else is altered.
        code_node["parameters"]["jsCode"] = target
        con.execute(
            "UPDATE workflow_entity SET nodes = ?, updatedAt = ? WHERE id = ?",
            (json.dumps(nodes), datetime.now(timezone.utc).isoformat(), wf_id),
        )
        con.commit()
        print("jsCode updated in n8n DB.")

        # Verify readback + webhook auth preservation.
        rb = con.execute(
            "SELECT nodes FROM workflow_entity WHERE id = ?", (wf_id,)
        ).fetchone()
        rb_nodes = json.loads(rb["nodes"])
        rb_code = next(n for n in rb_nodes if n.get("name") == CODE_NODE_NAME)
        rb_webhook = next((n for n in rb_nodes if n.get("name") == WEBHOOK_NODE_NAME), None)
        assert rb_code["parameters"]["jsCode"] == target, "readback jsCode mismatch"

        post_auth = None
        if rb_webhook is not None:
            post_auth = {
                "authentication": rb_webhook.get("parameters", {}).get("authentication"),
                "credentials": rb_webhook.get("credentials", {}),
            }
        print("\nVerification:")
        print("  jsCode readback matches repo: True")
        print(f"  webhook auth preserved:       {pre_auth == post_auth}")
        if post_auth:
            cred_ids = {
                k: v.get("id") for k, v in (post_auth.get("credentials") or {}).items()
            }
            print(f"  webhook authentication={post_auth.get('authentication')!r} credentials={cred_ids}")
        print("\nNext step (operator): docker compose restart n8n  (reloads the workflow)")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
