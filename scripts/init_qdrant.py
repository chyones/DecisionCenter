from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from apps.edr.config import settings

VECTOR_SIZE = 1024


def collection_name(project_code: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", project_code).strip("_").lower()
    if not normalized:
        raise ValueError("project_code must contain at least one alphanumeric character")
    return f"dc_{normalized}"


def project_codes_from_mapping(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("project_code"), str):
        return [data["project_code"]]
    if isinstance(data, list):
        return [
            item["project_code"]
            for item in data
            if isinstance(item, dict) and isinstance(item.get("project_code"), str)
        ]
    raise ValueError(f"{path} must contain a project_code object or a list of project objects")


def ensure_collection(client: QdrantClient, name: str) -> str:
    existing = {collection.name for collection in client.get_collections().collections}
    if name in existing:
        return "exists"

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        on_disk_payload=True,
    )
    return "created"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize Qdrant collections per project code.")
    parser.add_argument("--project-code", action="append", default=[], help="Project code to initialize.")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("docs/config/project_source_mapping.example.json"),
        help="Project source mapping JSON file used when --project-code is omitted.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_codes = args.project_code or project_codes_from_mapping(args.mapping)
    if not project_codes:
        raise SystemExit("No project codes supplied or found in mapping file.")

    client = QdrantClient(url=settings.qdrant_url)
    for project_code in project_codes:
        name = collection_name(project_code)
        status = ensure_collection(client, name)
        print(f"{name}: {status}")


if __name__ == "__main__":
    main()
