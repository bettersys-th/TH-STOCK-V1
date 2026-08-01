import os
import sys
import unittest
from unittest.mock import patch
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import update_and_build as pipeline
from market_validation import cross_check


class UpdatePipelineTests(unittest.TestCase):
    def test_price_update_corrects_existing_and_skips_zero_volume_rows(self):
        frame = pd.DataFrame({"Close": [10.5, 11.0], "Volume": [150, 0]},
                             index=pd.to_datetime(["2026-07-31", "2026-08-01"]))
        class FakeTicker:
            def history(self, **kwargs):
                self.kwargs = kwargs
                return frame
        prices = {"AAA": {"d": [20260731], "c": [10.0], "v": [100]}}
        with patch.object(pipeline.yf, "Ticker", return_value=FakeTicker()), patch.object(pipeline.time, "sleep"):
            updated, report = pipeline.update_prices(prices, ["AAA"])
        self.assertEqual(updated["AAA"]["c"], [10.5])
        self.assertEqual(updated["AAA"]["v"], [150])
        self.assertEqual(report["correctedTickers"], 1)
        self.assertEqual(report["newBarTickers"], 0)

    def test_action_merge_preserves_old_events_and_updates_same_date(self):
        old = {"AAA": [{"date": "2020-01-01", "ratio": 2.0}]}
        new = {"AAA": [{"date": "2020-01-01", "ratio": 3.0},
                        {"date": "2022-01-01", "ratio": 2.0}]}
        merged = pipeline.merge_actions(old, new, "ratio")
        self.assertEqual(merged["AAA"], [
            {"date": "2020-01-01", "ratio": 3.0},
            {"date": "2022-01-01", "ratio": 2.0},
        ])

    def test_action_merge_keeps_ticker_when_fetch_omits_it(self):
        old = {"AAA": [{"date": "2020-01-01", "amount": 1.0}]}
        self.assertEqual(pipeline.merge_actions(old, {}, "amount"), old)

    def test_quality_gate_rejects_collapsed_active_fetch(self):
        prices = {"AAA": {"d": [20260731], "c": [10], "v": [100]}}
        report = {"success": [], "empty": [], "errors": [{"ticker": "AAA", "error": "x"}]}
        actions = {"success": ["AAA"], "errors": []}
        with self.assertRaises(RuntimeError):
            pipeline.validate_store(prices, ["AAA"], report, actions)

    def test_cross_check_is_safe_without_api_keys(self):
        old_set = os.environ.pop("SET_API_KEY", None)
        old_twelve = os.environ.pop("TWELVE_DATA_API_KEY", None)
        try:
            result = cross_check({"AAA": {"c": [10]}}, ["AAA"])
            self.assertEqual(result["comparisonCount"], 0)
            self.assertTrue(all(not x["configured"] for x in result["providers"]))
        finally:
            if old_set is not None:
                os.environ["SET_API_KEY"] = old_set
            if old_twelve is not None:
                os.environ["TWELVE_DATA_API_KEY"] = old_twelve


if __name__ == "__main__":
    unittest.main()
