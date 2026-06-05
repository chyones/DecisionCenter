"""Bind 'DecisionCenter Webhook Header Auth' to the Receive Request webhook nodes
in the sharepoint_search, email_search, and owncloud_list n8n workflows.

Reads and writes the n8n SQLite database directly.  Safe to re-run (idempotent).
Requires the decisioncenter_n8n-data Docker volume to be accessible on the host.
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("/var/lib/docker/volumes/decisioncenter_n8n-data/_data/database.sqlite")
CREDENTIAL_NAME = "DecisionCenter Webhook Header Auth"
CREDENTIAL_TYPE = "httpHeaderAuth"
TARGET_WORKFLOWS = ("sharepoint_search", "email_search", "owncloud_list")


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row

    try:
        # Resolve credential id
        row = con.execute(
            "SELECT id, name, type FROM credentials_entity WHERE name = ?",
            (CREDENTIAL_NAME,),
        ).fetchone()
        if not row:
            print(f"ERROR: credential '{CREDENTIAL_NAME}' not found in n8n DB.", file=sys.stderr)
            return 1
        cred_id: str = row["id"]
        print(f"Credential found: name={row['name']!r}  type={row['type']!r}  id={cred_id!r}")

        updated = 0
        already_bound = 0

        for wf_name in TARGET_WORKFLOWS:
            wf_row = con.execute(
                "SELECT id, name, nodes FROM workflow_entity WHERE name = ?",
                (wf_name,),
            ).fetchone()
            if not wf_row:
                print(f"  SKIP {wf_name!r}: workflow not found in DB")
                continue

            wf_id: str = wf_row["id"]
            nodes: list[dict] = json.loads(wf_row["nodes"])
            changed = False

            for node in nodes:
                if node.get("name") != "Receive Request":
                    continue
                existing_creds = node.get("credentials", {})
                if (
                    CREDENTIAL_TYPE in existing_creds
                    and existing_creds[CREDENTIAL_TYPE].get("id") == cred_id
                ):
                    print(f"  OK (already bound): {wf_name!r} → Receive Request")
                    already_bound += 1
                    break

                # Add authentication parameter + credential binding (matches odoo_read pattern)
                node.setdefault("parameters", {})["authentication"] = "headerAuth"
                node["credentials"] = {
                    CREDENTIAL_TYPE: {"id": cred_id, "name": CREDENTIAL_NAME}
                }
                changed = True
                print(f"  BOUND: {wf_name!r} → Receive Request  (cred_id={cred_id!r})")
                break
            else:
                print(f"  SKIP {wf_name!r}: no 'Receive Request' node found")
                continue

            if changed:
                con.execute(
                    "UPDATE workflow_entity SET nodes = ? WHERE id = ?",
                    (json.dumps(nodes), wf_id),
                )
                updated += 1

        con.commit()
        print(f"\nDone: {updated} workflow(s) updated, {already_bound} already bound.")

        # Verification pass
        print("\nVerification:")
        for wf_name in TARGET_WORKFLOWS:
            wf_row = con.execute(
                "SELECT nodes FROM workflow_entity WHERE name = ?", (wf_name,)
            ).fetchone()
            if not wf_row:
                print(f"  {wf_name!r}: NOT FOUND")
                continue
            nodes = json.loads(wf_row["nodes"])
            for node in nodes:
                if node.get("name") == "Receive Request":
                    creds = node.get("credentials", {})
                    bound = CREDENTIAL_TYPE in creds and creds[CREDENTIAL_TYPE].get("id") == cred_id
                    auth = node.get("parameters", {}).get("authentication")
                    status = "BOUND" if bound else "NOT BOUND"
                    print(f"  {wf_name!r}: {status}  auth={auth!r}")
                    break

    finally:
        con.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
