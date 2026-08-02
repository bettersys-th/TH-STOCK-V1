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
        self.assertIn("/v1/summaries/cycles", html)
        self.assertIn("/v1/summaries/dca", html)
        self.assertIn("data/cycles_compact.json", html)
        self.assertIn("data/dca_compact.json", html)
        self.assertIn("let SIGNALS = [];", html)
        self.assertIn("let DATA=[];", html)
        self.assertIn("/v1/summaries/${name}", html)
        self.assertIn("/v1/summaries/swing", html)
        self.assertIn("['accumulation_signals.json','dividends.json']", html)
        self.assertIn("data/swing_signals.json", html)
        self.assertIn('class="nav-status-cluster"', html)
        for status_id in ("cycleSourceStatus", "scanSourceStatus", "swingSourceStatus", "dcaSourceStatus"):
            self.assertEqual(html.count(f'id="{status_id}"'), 1)


if __name__ == "__main__":
    unittest.main()
