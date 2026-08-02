import unittest

from scripts.accumulation import score_at, split_adjust


class AccumulationTests(unittest.TestCase):
    def test_split_adjusts_price_and_volume_in_opposite_directions(self):
        p, v = split_adjust([20200101, 20200201], [100, 10], [100, 1000], [(20200201, 10)])
        self.assertEqual(p, [10.0, 10.0])
        self.assertEqual(v, [1000.0, 1000.0])

    def test_score_does_not_use_future_bars(self):
        dates = list(range(20200000, 20200320))
        close = [100 - min(i, 100) * .3 for i in range(320)]
        volume = [10000 + (i % 7) * 100 for i in range(320)]
        before = score_at(dates, close, volume, 280)
        close[281:] = [9999] * (len(close) - 281)
        volume[281:] = [99999999] * (len(volume) - 281)
        after = score_at(dates, close, volume, 280)
        self.assertEqual(before, after)

    def test_warns_when_traded_value_is_very_low_for_30_sessions(self):
        dates = list(range(20200000, 20200320))
        close = [1.0] * 320
        volume = [100_000] * 320
        signal = score_at(dates, close, volume)
        self.assertTrue(signal["lowLiquidity30"])
        self.assertEqual(signal["avgVolume30"], 100_000)

    def test_exposes_recent_volume_and_momentum_for_screening(self):
        dates = list(range(20200000, 20200320))
        close = [10.0] * 315 + [10.0, 10.2, 10.4, 10.6, 11.0]
        volume = [100_000] * 315 + [200_000] * 5
        signal = score_at(dates, close, volume)
        self.assertEqual(signal["volume5Ratio"], 2.0)
        self.assertEqual(signal["avgVolume5"], 200_000)
        self.assertGreater(signal["momentum5"], 0)


if __name__ == "__main__":
    unittest.main()
