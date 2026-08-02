"""Report and optionally delete orphaned immutable objects from staging Storage."""

from __future__ import annotations

import argparse
import json
import os

MANAGED_PREFIX = "o_"


class AppwriteRemote:
    def __init__(self):
        from appwrite.client import Client
        from appwrite.query import Query
        from appwrite.services.storage import Storage

        required = ["APPWRITE_ENDPOINT", "APPWRITE_PROJECT_ID", "APPWRITE_API_KEY", "APPWRITE_MARKET_BUCKET_ID"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise RuntimeError("missing Appwrite environment variables: " + ", ".join(missing))
        client = (
            Client()
            .set_endpoint(os.environ["APPWRITE_ENDPOINT"])
            .set_project(os.environ["APPWRITE_PROJECT_ID"])
            .set_key(os.environ["APPWRITE_API_KEY"])
        )
        self.storage = Storage(client)
        self.query = Query
        self.bucket_id = os.environ["APPWRITE_MARKET_BUCKET_ID"]

    def list_files(self) -> list[dict]:
        files = []
        offset = 0
        while True:
            page = self.storage.list_files(
                bucket_id=self.bucket_id,
                queries=[self.query.limit(100), self.query.offset(offset)],
                total=False,
            )
            batch = [
                {"id": item.id, "name": item.name, "createdAt": item.createdat, "bytes": int(item.sizeoriginal)}
                for item in page.files
            ]
            files.extend(batch)
            if len(batch) < 100:
                return files
            offset += len(batch)

    def download(self, file_id: str) -> bytes:
        return self.storage.get_file_download(bucket_id=self.bucket_id, file_id=file_id)

    def delete(self, file_id: str) -> None:
        self.storage.delete_file(bucket_id=self.bucket_id, file_id=file_id)


def cleanup(remote, apply: bool = False) -> dict:
    files = remote.list_files()
    manifests = [item for item in files if item["name"] == "manifest.json"]
    if not manifests:
        raise RuntimeError("no completed manifest.json exists; refusing cleanup")
    current = max(manifests, key=lambda item: item["createdAt"])
    downloaded = remote.download(current["id"])
    if isinstance(downloaded, dict):
        manifest = downloaded
    elif isinstance(downloaded, bytes):
        manifest = json.loads(downloaded.decode("utf-8"))
    elif isinstance(downloaded, str):
        manifest = json.loads(downloaded)
    else:
        raise RuntimeError(f"unsupported manifest response type: {type(downloaded).__name__}")
    if manifest.get("schemaVersion") != 1 or not manifest.get("tickers"):
        raise RuntimeError("newest manifest is invalid; refusing cleanup")

    referenced = {
        metadata.get("fileId")
        for metadata in list(manifest["tickers"].values()) + list(manifest.get("summaries", {}).values())
    }
    if None in referenced:
        raise RuntimeError("manifest lacks remote file IDs; refusing cleanup")
    keep = referenced | {current["id"]}
    remote_ids = {item["id"] for item in files}
    missing = sorted(keep - remote_ids)
    if missing:
        raise RuntimeError(f"manifest references {len(missing)} missing objects; refusing cleanup")

    # Unknown/manual files are never deleted. Only our content-addressed objects
    # and superseded manifests are eligible.
    managed = [item for item in files if item["id"].startswith(MANAGED_PREFIX)]
    orphans = [item for item in managed if item["id"] not in keep]
    report = {
        "remoteFiles": len(files),
        "keep": len(keep),
        "orphans": len(orphans),
        "orphanBytes": sum(item["bytes"] for item in orphans),
        "currentManifestFileId": current["id"],
        "deleted": 0,
    }
    if apply:
        for item in orphans:
            remote.delete(item["id"])
            report["deleted"] += 1
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean orphaned Appwrite staging market objects")
    parser.add_argument("--apply", action="store_true", help="delete verified orphans; default is dry-run")
    args = parser.parse_args()
    report = cleanup(AppwriteRemote(), apply=args.apply)
    print(f"Appwrite cleanup {'applied' if args.apply else 'dry-run'}: {json.dumps(report, separators=(',', ':'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
