import unittest

from audit_data import build_price_coverage


class PriceCoverageTests(unittest.TestCase):
    def test_detects_gap_from_observed_market_calendar(self):
        market_dates = [20260102, 20260105, 20260106, 20260107, 20260108]
        prices = {}
        tickers = []
        for i in range(12):
            ticker = f"A{i:02d}"
            tickers.append(ticker)
            dates = market_dates if i else market_dates[:2] + market_dates[3:]
            prices[ticker] = {"d": dates, "c": [10] * len(dates), "v": [100] * len(dates)}
        report = build_price_coverage(prices, tickers, market_dates[-1])
        first = next(row for row in report["tickers"] if row["ticker"] == "A00")
        self.assertEqual(first["status"], "gaps")
        self.assertEqual(first["missingRecentDates"], ["20260106"])

    def test_reports_recent_ohlc_completeness(self):
        dates = [20260102, 20260105, 20260106, 20260107, 20260108]
        raw = {"d": dates, "c": [10] * 5, "v": [100] * 5,
               "o": [9] * 5, "h": [11] * 5, "lo": [8] * 5}
        report = build_price_coverage({"AAA": raw}, ["AAA"], dates[-1])
        self.assertTrue(report["tickers"][0]["ohlcLast5Complete"])


if __name__ == "__main__":
    unittest.main()
