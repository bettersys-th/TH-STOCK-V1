import gzip
import importlib.util
import json
import os
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "appwrite" / "functions" / "market-api" / "handler.py"
spec = importlib.util.spec_from_file_location("market_api", MODULE_PATH)
market_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(market_api)

COMPAT_PATH = MODULE_PATH.with_name("main.py")
compat_spec = importlib.util.spec_from_file_location("market_api_compat", COMPAT_PATH)
market_api_compat = importlib.util.module_from_spec(compat_spec)
compat_spec.loader.exec_module(market_api_compat)


class FakeRepository:
    def __init__(self):
        self.manifest = {
            "schemaVersion": 1,
            "dataAsOf": 20260731,
            "tickerCount": 1,
            "tickers": {"PTT": {"fileId": "o_stock"}},
            "summaries": {},
        }
        self.stock = {"schemaVersion": 1, "ticker": "PTT", "d": [20260731], "c": [30.0], "v": [100]}

    def current_version(self):
        return {"manifestFileId": "o_manifest", "schemaVersion": 1, "dataAsOf": 20260731}

    def download(self, file_id):
        if file_id == "o_manifest":
            return self.manifest
        return gzip.compress(json.dumps(self.stock).encode())


class MarketApiTests(unittest.TestCase):
    def setUp(self):
        market_api._manifest_cache.update({"expires": 0.0, "fileId": None, "value": None})

    def test_reads_published_stock(self):
        version, stock = market_api.MarketService(FakeRepository()).stock("ptt")
        self.assertEqual(version["dataAsOf"], 20260731)
        self.assertEqual(stock["ticker"], "PTT")
        self.assertEqual(stock["v"], [100])

    def test_compatibility_entrypoint_loads_handler(self):
        self.assertTrue(callable(market_api_compat.main))
        self.assertEqual(market_api_compat.main.__name__, market_api.main.__name__)

    def test_rejects_unknown_and_invalid_ticker(self):
        service = market_api.MarketService(FakeRepository())
        with self.assertRaises(LookupError):
            service.stock("UNKNOWN")
        with self.assertRaises(LookupError):
            service.stock("../PTT")

    def test_rejects_pointer_manifest_mismatch(self):
        repo = FakeRepository()
        repo.manifest["dataAsOf"] = 20260730
        with self.assertRaisesRegex(ValueError, "date"):
            market_api.MarketService(repo).manifest()

    def test_cors_is_exact_allowlist(self):
        old = os.environ.get("ALLOWED_ORIGINS")
        os.environ["ALLOWED_ORIGINS"] = "https://example.com,https://bettersys-th.github.io"
        try:
            self.assertEqual(market_api._allowed_origin("https://example.com"), "https://example.com")
            self.assertIsNone(market_api._allowed_origin("https://evil.example.com"))
        finally:
            if old is None:
                os.environ.pop("ALLOWED_ORIGINS", None)
            else:
                os.environ["ALLOWED_ORIGINS"] = old


if __name__ == "__main__":
    unittest.main()
