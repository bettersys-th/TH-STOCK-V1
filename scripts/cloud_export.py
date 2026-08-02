"""Build provider-neutral, cloud-ready market-data objects.

The current single-file website remains unchanged. These objects are the future
Storage/API contract and can be uploaded to Appwrite without exposing API keys.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
SUMMARY_FILES = {
    "cycles": "cycles_compact.json",
    "dividends": "dividends.json",
    "accumulation": "accumulation_signals.json",
    "swing": "swing_signals.json",
    "dca": "dca_compact.json",
}


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _write_gzip(path: Path, value) -> tuple[int, str]:
    # mtime=0 makes identical input produce identical bytes and checksums.
    raw = _json_bytes(value)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return len(compressed), hashlib.sha256(compressed).hexdigest()


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def verify_cloud_export(export_dir: str | Path, prices: dict) -> dict:
    export_path = Path(export_dir)
    manifest = _read_json(export_path / "manifest.json", None)
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("invalid or missing cloud manifest")
    expected = {ticker for ticker, entry in prices.items() if entry.get("d")}
    actual = set(manifest.get("tickers", {}))
    if actual != expected:
        missing = sorted(expected - actual)[:5]
        extra = sorted(actual - expected)[:5]
        raise ValueError(f"cloud ticker mismatch; missing={missing}, extra={extra}")
    total_bars = 0
    for ticker, metadata in manifest["tickers"].items():
        object_path = export_path / metadata["path"]
        compressed = object_path.read_bytes()
        if hashlib.sha256(compressed).hexdigest() != metadata["sha256"]:
            raise ValueError(f"checksum mismatch for {ticker}")
        with gzip.open(object_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        source = prices[ticker]
        if payload.get("ticker") != ticker or any(payload.get(key) != source.get(key) for key in ("d", "c", "v")):
            raise ValueError(f"cloud payload mismatch for {ticker}")
        total_bars += len(payload["d"])
    if total_bars != manifest.get("totalBars"):
        raise ValueError("cloud totalBars mismatch")
    return manifest


def build_cloud_export(prices: dict, data_dir: str | Path, output_dir: str | Path | None = None) -> dict:
    data_path = Path(data_dir).resolve()
    target = Path(output_dir).resolve() if output_dir else data_path / "cloud_market"
    if target == data_path or data_path not in target.parents:
        raise ValueError("cloud export must be a child of the data directory")

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".cloud-market-", dir=target.parent))
    try:
        ticker_manifest = {}
        newest_date = 0
        total_bars = 0
        for ticker in sorted(prices):
            entry = prices[ticker]
            dates = entry.get("d", [])
            closes = entry.get("c", [])
            volumes = entry.get("v", [])
            if not dates:
                continue
            if not (len(dates) == len(closes) == len(volumes)):
                raise ValueError(f"misaligned price arrays for {ticker}")
            payload = {
                "schemaVersion": SCHEMA_VERSION,
                "ticker": ticker,
                "market": "SET",
                "currency": "THB",
                "d": dates,
                "c": closes,
                "v": volumes,
            }
            relative = f"stocks/{ticker}.json.gz"
            size, checksum = _write_gzip(staging / relative, payload)
            ticker_manifest[ticker] = {
                "path": relative,
                "bars": len(dates),
                "firstDate": dates[0],
                "lastDate": dates[-1],
                "bytes": size,
                "sha256": checksum,
            }
            newest_date = max(newest_date, dates[-1])
            total_bars += len(dates)

        summaries = {}
        for name, filename in SUMMARY_FILES.items():
            source = data_path / filename
            if not source.exists():
                continue
            relative = f"summaries/{name}.json.gz"
            value = _read_json(source, {} if name in {"cycles", "dividends", "dca"} else [])
            size, checksum = _write_gzip(staging / relative, value)
            summaries[name] = {"path": relative, "bytes": size, "sha256": checksum}

        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "market": "SET",
            "currency": "THB",
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dataAsOf": newest_date or None,
            "tickerCount": len(ticker_manifest),
            "totalBars": total_bars,
            "tickers": ticker_manifest,
            "summaries": summaries,
        }
        (staging / "manifest.json").write_bytes(_json_bytes(manifest))
        verify_cloud_export(staging, prices)

        backup = target.with_name(target.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            os.replace(target, backup)
        os.replace(staging, target)
        if backup.exists():
            shutil.rmtree(backup)
        return manifest
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
