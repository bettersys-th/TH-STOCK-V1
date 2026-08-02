"""Upload verified cloud-market objects to a private Appwrite bucket.

Dry-run is the default. Use --apply only with server-side environment secrets.
Objects are immutable and content-addressed; the data_versions table will become
the atomic pointer in the next migration step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT = ROOT / "data" / "cloud_market"


def object_id(checksum: str) -> str:
    return "o_" + checksum[:32]


def load_upload_plan(export_dir: Path) -> tuple[dict, list[dict]]:
    manifest_path = export_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    objects = []
    for metadata in list(manifest["tickers"].values()) + list(manifest["summaries"].values()):
        objects.append({
            "fileId": object_id(metadata["sha256"]),
            "path": metadata["path"],
            "sha256": metadata["sha256"],
            "bytes": metadata["bytes"],
        })
    objects.sort(key=lambda item: item["path"])
    return manifest, objects


def remote_manifest(manifest: dict, objects: list[dict]) -> bytes:
    result = json.loads(json.dumps(manifest))
    ids = {item["path"]: item["fileId"] for item in objects}
    for metadata in list(result["tickers"].values()) + list(result["summaries"].values()):
        metadata["fileId"] = ids[metadata["path"]]
    return json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class AppwriteStorage:
    def __init__(self, endpoint: str, project_id: str, api_key: str, bucket_id: str):
        from appwrite.client import Client
        from appwrite.exception import AppwriteException
        from appwrite.input_file import InputFile
        from appwrite.services.storage import Storage
        from appwrite.services.tables_db import TablesDB

        self._exception = AppwriteException
        self._input_file = InputFile
        self._bucket_id = bucket_id
        self._database_id = os.environ.get("APPWRITE_DATABASE_ID", "app")
        self._versions_table_id = os.environ.get("APPWRITE_DATA_VERSIONS_TABLE_ID", "data_versions")
        client = Client().set_endpoint(endpoint).set_project(project_id).set_key(api_key)
        self._storage = Storage(client)
        self._tables = TablesDB(client)

    def exists(self, file_id: str) -> bool:
        try:
            self._storage.get_file(bucket_id=self._bucket_id, file_id=file_id)
            return True
        except self._exception as exc:
            if getattr(exc, "code", None) == 404:
                return False
            raise

    def upload_path(self, file_id: str, path: Path) -> None:
        self._storage.create_file(
            bucket_id=self._bucket_id,
            file_id=file_id,
            file=self._input_file.from_path(str(path)),
            permissions=[],
        )

    def upload_bytes(self, file_id: str, content: bytes, filename: str) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / filename
            path.write_bytes(content)
            self.upload_path(file_id, path)

    def publish_version(self, manifest_file_id: str, manifest: dict, channel: str = "staging") -> None:
        self._tables.upsert_row(
            database_id=self._database_id,
            table_id=self._versions_table_id,
            row_id=channel,
            data={
                "channel": channel,
                "manifestFileId": manifest_file_id,
                "dataAsOf": int(manifest["dataAsOf"]),
                "schemaVersion": int(manifest["schemaVersion"]),
                "publishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            permissions=[],
        )


def upload(export_dir: Path, storage=None, apply: bool = False) -> dict:
    manifest, objects = load_upload_plan(export_dir)
    # verify_cloud_export requires the source prices and is run during export; here
    # checksums protect the boundary immediately before network upload.
    for item in objects:
        content = (export_dir / item["path"]).read_bytes()
        if len(content) != item["bytes"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"local upload object failed integrity check: {item['path']}")

    report = {"objects": len(objects), "bytes": sum(x["bytes"] for x in objects), "uploaded": 0, "skipped": 0, "published": False}
    if not apply:
        return report
    if storage is None:
        required = ["APPWRITE_ENDPOINT", "APPWRITE_PROJECT_ID", "APPWRITE_API_KEY", "APPWRITE_MARKET_BUCKET_ID"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise RuntimeError("missing Appwrite environment variables: " + ", ".join(missing))
        storage = AppwriteStorage(*(os.environ[name] for name in required))

    for item in objects:
        if storage.exists(item["fileId"]):
            report["skipped"] += 1
        else:
            storage.upload_path(item["fileId"], export_dir / item["path"])
            report["uploaded"] += 1

    content = remote_manifest(manifest, objects)
    manifest_checksum = hashlib.sha256(content).hexdigest()
    manifest_id = object_id(manifest_checksum)
    if storage.exists(manifest_id):
        report["skipped"] += 1
    else:
        storage.upload_bytes(manifest_id, content, "manifest.json")
        report["uploaded"] += 1
    report["manifestFileId"] = manifest_id
    if not hasattr(storage, "publish_version"):
        raise RuntimeError("storage adapter cannot publish data_versions pointer")
    storage.publish_version(manifest_id, manifest)
    report["published"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload cloud market data to Appwrite Storage")
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--apply", action="store_true", help="perform network writes; default is dry-run")
    args = parser.parse_args()
    report = upload(args.export_dir.resolve(), apply=args.apply)
    mode = "uploaded" if args.apply else "dry-run"
    print(f"Appwrite {mode}: {json.dumps(report, separators=(',', ':'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
