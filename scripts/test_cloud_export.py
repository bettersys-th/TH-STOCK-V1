import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from cloud_export import build_cloud_export, verify_cloud_export


class CloudExportTests(unittest.TestCase):
    def test_export_splits_tickers_and_reports_integrity(self):
        prices = {
            "BBB": {"d": [20260102], "c": [20.0], "v": [200]},
            "AAA": {"d": [20260102, 20260105], "c": [10.0, 10.5], "v": [100, 120]},
        }
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp) / "data"
            data_dir.mkdir()
            (data_dir / "cycles_compact.json").write_text('{"AAA":{"e":[]}}', encoding="utf-8")
            output = data_dir / "cloud_market"
            manifest = build_cloud_export(prices, data_dir, output)

            self.assertEqual(manifest["tickerCount"], 2)
            self.assertEqual(manifest["totalBars"], 3)
            self.assertEqual(manifest["dataAsOf"], 20260105)
            self.assertIn("cycles", manifest["summaries"])
            with gzip.open(output / "stocks" / "AAA.json.gz", "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["ticker"], "AAA")
            self.assertEqual(payload["d"], prices["AAA"]["d"])
            self.assertEqual(payload["v"], prices["AAA"]["v"])
            self.assertEqual(len(manifest["tickers"]["AAA"]["sha256"]), 64)
            self.assertEqual(verify_cloud_export(output, prices)["tickerCount"], 2)

            with (output / "stocks" / "AAA.json.gz").open("ab") as handle:
                handle.write(b"tampered")
            with self.assertRaisesRegex(ValueError, "checksum mismatch for AAA"):
                verify_cloud_export(output, prices)

    def test_export_rejects_misaligned_price_arrays(self):
        prices = {"BAD": {"d": [20260102], "c": [], "v": [1]}}
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp) / "data"
            data_dir.mkdir()
            with self.assertRaisesRegex(ValueError, "misaligned price arrays for BAD"):
                build_cloud_export(prices, data_dir)

    def test_existing_export_is_updated_without_directory_rename(self):
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp) / "data"
            output = data_dir / "cloud_market"
            output.mkdir(parents=True)
            locked_placeholder = output / "keep-unreferenced.txt"
            locked_placeholder.write_text("retained", encoding="utf-8")
            prices = {"AAA": {"d": [20260102], "c": [10.0], "v": [100]}}
            build_cloud_export(prices, data_dir, output)
            self.assertTrue((output / "stocks" / "AAA.json.gz").exists())
            self.assertEqual(locked_placeholder.read_text(encoding="utf-8"), "retained")


if __name__ == "__main__":
    unittest.main()
