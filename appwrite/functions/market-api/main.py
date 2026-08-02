"""Read-only Appwrite Function for versioned SET market data."""

from __future__ import annotations

import gzip
import json
import os
import re
import time

from appwrite.client import Client
from appwrite.services.storage import Storage
from appwrite.services.tables_db import TablesDB

TICKER_RE = re.compile(r"^[A-Z0-9.-]{1,24}$")
DATABASE_ID = os.environ.get("MARKET_DATABASE_ID", "app")
VERSIONS_TABLE_ID = os.environ.get("MARKET_VERSIONS_TABLE_ID", "data_versions")
BUCKET_ID = os.environ.get("MARKET_BUCKET_ID", "market-data")
CHANNEL = os.environ.get("MARKET_CHANNEL", "staging")
MANIFEST_TTL_SECONDS = 60
_manifest_cache = {"expires": 0.0, "fileId": None, "value": None}


def _as_json(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, bytes):
        return json.loads(value.decode("utf-8"))
    if isinstance(value, str):
        return json.loads(value)
    raise TypeError(f"unsupported JSON response type: {type(value).__name__}")


class MarketRepository:
    def __init__(self, api_key: str):
        client = (
            Client()
            .set_endpoint(os.environ["APPWRITE_FUNCTION_API_ENDPOINT"])
            .set_project(os.environ["APPWRITE_FUNCTION_PROJECT_ID"])
            .set_key(api_key)
        )
        self.tables = TablesDB(client)
        self.storage = Storage(client)

    def current_version(self) -> dict:
        row = self.tables.get_row(
            database_id=DATABASE_ID,
            table_id=VERSIONS_TABLE_ID,
            row_id=CHANNEL,
        )
        data = row.data
        return data.model_dump() if hasattr(data, "model_dump") else dict(data)

    def download(self, file_id: str):
        return self.storage.get_file_download(bucket_id=BUCKET_ID, file_id=file_id)


class MarketService:
    def __init__(self, repository):
        self.repository = repository

    def manifest(self) -> tuple[dict, dict]:
        version = self.repository.current_version()
        file_id = version["manifestFileId"]
        now = time.monotonic()
        if _manifest_cache["fileId"] == file_id and _manifest_cache["expires"] > now:
            return version, _manifest_cache["value"]
        manifest = _as_json(self.repository.download(file_id))
        if manifest.get("schemaVersion") != version.get("schemaVersion"):
            raise ValueError("manifest schema does not match published pointer")
        if manifest.get("dataAsOf") != version.get("dataAsOf"):
            raise ValueError("manifest date does not match published pointer")
        _manifest_cache.update({"fileId": file_id, "expires": now + MANIFEST_TTL_SECONDS, "value": manifest})
        return version, manifest

    def stock(self, ticker: str) -> tuple[dict, dict]:
        ticker = ticker.upper()
        if not TICKER_RE.fullmatch(ticker):
            raise LookupError("invalid ticker")
        version, manifest = self.manifest()
        metadata = manifest.get("tickers", {}).get(ticker)
        if not metadata:
            raise LookupError("ticker not found")
        compressed = self.repository.download(metadata["fileId"])
        if not isinstance(compressed, bytes):
            raise ValueError("stock object is not binary gzip data")
        payload = json.loads(gzip.decompress(compressed).decode("utf-8"))
        if payload.get("ticker") != ticker or payload.get("schemaVersion") != manifest.get("schemaVersion"):
            raise ValueError("stock payload integrity mismatch")
        return version, payload


def _allowed_origin(request_origin: str | None) -> str | None:
    configured = {value.strip() for value in os.environ.get("ALLOWED_ORIGINS", "").split(",") if value.strip()}
    if request_origin and request_origin in configured:
        return request_origin
    return None


def _headers(origin: str | None, max_age: int = 60) -> dict:
    headers = {
        "cache-control": f"public, max-age={max_age}, stale-while-revalidate=300",
        "x-content-type-options": "nosniff",
        "vary": "Origin",
    }
    if origin:
        headers.update({
            "access-control-allow-origin": origin,
            "access-control-allow-methods": "GET, OPTIONS",
            "access-control-allow-headers": "Content-Type",
            "access-control-max-age": "86400",
        })
    return headers


def main(context):
    origin = _allowed_origin(context.req.headers.get("origin"))
    if context.req.method == "OPTIONS":
        if context.req.headers.get("origin") and not origin:
            return context.res.json({"error": "origin_not_allowed"}, 403, _headers(None, 0))
        return context.res.empty(204, _headers(origin, 0))
    if context.req.method != "GET":
        return context.res.json({"error": "method_not_allowed"}, 405, _headers(origin, 0))

    try:
        api_key = context.req.headers.get("x-appwrite-key")
        if not api_key:
            raise RuntimeError("dynamic function API key is unavailable")
        service = MarketService(MarketRepository(api_key))
        path = context.req.path.rstrip("/") or "/"
        if path in {"/", "/health"}:
            version, manifest = service.manifest()
            return context.res.json({
                "ok": True,
                "channel": CHANNEL,
                "dataAsOf": version["dataAsOf"],
                "schemaVersion": version["schemaVersion"],
                "tickerCount": manifest["tickerCount"],
            }, 200, _headers(origin, 30))
        if path == "/v1/manifest":
            version, manifest = service.manifest()
            return context.res.json({
                "channel": CHANNEL,
                "dataAsOf": version["dataAsOf"],
                "schemaVersion": version["schemaVersion"],
                "tickerCount": manifest["tickerCount"],
                "tickers": sorted(manifest["tickers"]),
                "summaries": sorted(manifest.get("summaries", {})),
            }, 200, _headers(origin, 300))
        prefix = "/v1/stocks/"
        if path.startswith(prefix) and "/" not in path[len(prefix):]:
            version, payload = service.stock(path[len(prefix):])
            return context.res.json({"dataAsOf": version["dataAsOf"], "stock": payload}, 200, _headers(origin, 3600))
        return context.res.json({"error": "not_found"}, 404, _headers(origin, 0))
    except LookupError as exc:
        return context.res.json({"error": str(exc).replace(" ", "_")}, 404, _headers(origin, 0))
    except Exception as exc:
        context.error(f"market-api failure: {type(exc).__name__}: {exc}")
        return context.res.json({"error": "service_unavailable"}, 503, _headers(origin, 0))
