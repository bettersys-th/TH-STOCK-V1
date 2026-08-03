import unittest
from datetime import date, timedelta

from scripts.strategy_data import build_dca_compact, build_swing_signals, swing_signal_at


class StrategyDataTests(unittest.TestCase):
    def test_dca_monthly_uses_last_close_and_adjusts_old_split(self):
        dates = [20200000 + month * 100 + day for month in range(1, 13) for day in (1, 15, 28)]
        close = [100.0] * len(dates)
        close[2], close[5] = 110, 60
        prices = {"AAA": {"d": dates, "c": close, "v": [100] * len(dates)}}
        splits = {"AAA": [{"date": "2020-02-01", "ratio": 2}]}
        result = build_dca_compact(prices, splits, {}, ["AAA"])
        self.assertEqual(result["AAA"]["m"][:2], [["2020-01", 55.0], ["2020-02", 60.0]])
        latest = result["AAA"]["m"][-1][1]
        self.assertGreater(result["AAA"]["r"]["peak"], latest)
        self.assertLess(result["AAA"]["r"]["trough"], latest)
        self.assertIn("downDaysMedian", result["AAA"]["r"])
        self.assertIn("liquidityTrend30", result["AAA"]["r"])
        self.assertIn("daysSinceHigh252", result["AAA"]["r"])
        self.assertEqual(len(result["AAA"]["p3"]), len(close))
        self.assertEqual(result["AAA"]["p3"][-1], close[-1])

    def test_swing_signal_is_point_in_time_latest(self):
        dates = [int((date(2025, 1, 1) + timedelta(days=i)).strftime("%Y%m%d")) for i in range(300)]
        close = [10 + i * .01 for i in range(300)]
        volume = [1_000_000] * 300
        rows = build_swing_signals({"AAA": {"d": dates, "c": close, "v": volume}}, {}, ["AAA"])
        self.assertEqual(rows[0]["t"], "AAA")
        self.assertIn(rows[0]["status"], {"triggered", "setup", "extended"})

    def test_swing_signal_ignores_bars_after_evaluation_date(self):
        dates = [int((date(2025, 1, 1) + timedelta(days=i)).strftime("%Y%m%d")) for i in range(300)]
        close = [10 + i * .01 for i in range(300)]
        volume = [1_000_000] * 300
        before = swing_signal_at("AAA", dates, close, volume, 250)
        close[251:] = [9999] * 49
        volume[251:] = [99999999] * 49
        after = swing_signal_at("AAA", dates, close, volume, 250)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
