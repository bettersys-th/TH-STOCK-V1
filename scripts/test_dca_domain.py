import json
import subprocess
import unittest
from pathlib import Path


DOMAIN = Path(__file__).parent / "templates" / "dca_domain.js"


def run_domain(expression):
    script = f"const d=require({json.dumps(str(DOMAIN))}); console.log(JSON.stringify({expression}));"
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    )
    return json.loads(completed.stdout)


class DcaDomainBaselineTests(unittest.TestCase):
    def test_board_lot_requires_100_shares_and_carries_remainder(self):
        self.assertEqual(run_domain("d.boardLotPurchase(4999,50)"), {"shares": 0, "cost": 0})
        self.assertEqual(run_domain("d.boardLotPurchase(5000,50)"), {"shares": 100, "cost": 5000})
        self.assertEqual(run_domain("d.boardLotPurchase(12550,50)"), {"shares": 200, "cost": 10000})

    def test_contribution_uses_remaining_budget_and_frequency(self):
        daily = run_domain("d.contributionPerPeriod({budget:130000,initial:10000,months:24,frequency:'daily'})")
        weekly = run_domain("d.contributionPerPeriod({budget:130000,initial:10000,months:24,frequency:'weekly'})")
        monthly = run_domain("d.contributionPerPeriod({budget:130000,initial:10000,months:24,frequency:'monthly'})")
        self.assertAlmostEqual(daily, 120000 / (24 * 21))
        self.assertAlmostEqual(weekly, 1250)
        self.assertAlmostEqual(monthly, 5000)

    def test_scenario_baseline_without_dividend(self):
        result = run_domain("d.simulateScenario({current:10,bottom:8,target:12,steps:4,downSteps:2,initial:1000,contribution:1000,budget:5000,annualDiv:0,periodsPerYear:12})")
        self.assertEqual(result["invested"], 4900)
        self.assertEqual(result["value"], 6000)
        self.assertEqual(result["pnl"], 1100)
        self.assertAlmostEqual(result["pct"], 1100 / 4900 * 100)
        self.assertLess(result["worst"], 0)

    def test_presets_keep_market_assumptions_separate(self):
        presets = run_domain("d.SCENARIO_PRESETS")
        self.assertTrue(presets["cycle"]["useCycleReference"])
        self.assertIsNone(presets["cycle"]["drawdownPercent"])
        self.assertEqual(presets["correction"]["drawdownPercent"], 25)
        self.assertEqual(presets["crisis"]["recoveryMode"], "none")


if __name__ == "__main__":
    unittest.main()
