import tempfile
import unittest
from pathlib import Path

from scripts.build_toolkit_html import build


class ToolkitBuildTests(unittest.TestCase):
    def test_cycle_and_dca_payloads_are_lazy_loaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "index.html"
            build(temp_dir, output)
            html = output.read_text(encoding="utf-8")

        self.assertIn("let CYCLES = {};", html)
        self.assertIn("let DATA={};", html)
        self.assertIn("fetchMarketSummary('cycles'", html)
        self.assertIn("fetchMarketSummary('dca'", html)
        self.assertIn("data/cycles_compact.json", html)
        self.assertIn("data/dca_compact.json", html)
        self.assertIn("let SIGNALS = [];", html)
        self.assertIn("let DATA=[];", html)
        self.assertIn("/v1/summaries/${name}", html)
        self.assertIn("['accumulation_signals.json','dividends.json']", html)
        self.assertIn("data/swing_signals.json", html)
        self.assertIn('class="nav-status-cluster"', html)
        for status_id in ("cycleSourceStatus", "scanSourceStatus", "swingSourceStatus", "dcaSourceStatus"):
            self.assertEqual(html.count(f'id="{status_id}"'), 1)
        self.assertNotIn('id="navCalc"', html)
        self.assertNotIn('id="pageCalc"', html)
        self.assertIn('<button class="nav-tab active" id="navScan">', html)
        self.assertIn("window.ensureCycleData = loadCloudCycles", html)
        self.assertGreaterEqual(html.count("await window.ensureCycleData?.()"), 2)
        self.assertIn("const MARKET_CACHE_NAME = 'th-stock-market-v1'", html)
        self.assertIn("async function fetchMarketSummary(name, signal)", html)
        self.assertIn("MARKET_CACHE_TTL_MS", html)
        self.assertIn("fetchMarketSummary('swing')", html)
        self.assertIn("map(name=>fetchMarketSummary(name))", html)
        self.assertIn("function setCloudSummaryStatus", html)
        self.assertIn("payload._clientSource = 'cache'", html)
        self.assertIn("เก่ากว่าวันปัจจุบัน", html)
        self.assertIn('id="recentOhlcRow"', html)
        self.assertIn("function renderRecentOhlc(stock)", html)
        self.assertIn('id="scanVolume5RatioMin"', html)
        self.assertIn("function trendInfo(s)", html)
        self.assertIn("🔎 คัดกรองหุ้น", html)
        self.assertIn("Cloud screener schema is older than this page", html)


if __name__ == "__main__":
    unittest.main()
