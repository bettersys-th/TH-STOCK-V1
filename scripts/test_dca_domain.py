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

    def test_contribution_splits_monthly_budget_by_frequency(self):
        daily = run_domain("d.contributionPerPeriod({monthlyBudget:5000,frequency:'daily'})")
        weekly = run_domain("d.contributionPerPeriod({monthlyBudget:5000,frequency:'weekly'})")
        monthly = run_domain("d.contributionPerPeriod({monthlyBudget:5000,frequency:'monthly'})")
        self.assertAlmostEqual(daily, 5000 / 21)
        self.assertAlmostEqual(weekly, 1250)
        self.assertAlmostEqual(monthly, 5000)

    def test_scenario_baseline_without_dividend(self):
        result = run_domain("d.simulateScenario({current:10,bottom:8,target:12,steps:4,downSteps:2,initial:1000,contribution:1000,budget:5000,annualDiv:0,periodsPerYear:12})")
        self.assertEqual(result["invested"], 4900)
        self.assertEqual(result["value"], 6000)
        self.assertEqual(result["pnl"], 1100)
        self.assertAlmostEqual(result["pct"], 1100 / 4900 * 100)
        self.assertLess(result["worst"], 0)

    def test_monthly_budget_fit_uses_one_hundred_share_lot(self):
        fit = run_domain("d.assessMonthlyBudget({monthlyBudget:5000,currentPrice:40,initial:0})")
        wait = run_domain("d.assessMonthlyBudget({monthlyBudget:3500,currentPrice:120,initial:10000})")
        self.assertEqual(fit["status"], "fit")
        self.assertEqual(fit["lotCost"], 4000)
        self.assertEqual(wait["status"], "accumulate")
        self.assertEqual(wait["monthsUntilFirstLot"], 1)
        self.assertEqual(wait["monthsPerLot"], 4)

    def test_affordable_alternatives_are_ranked_by_price_performance(self):
        expression = "d.rankAffordableAlternatives({stocks:{A:{m:[['2026-01',100]],r:{return60:5,maxDrawdown:-20,medianValue30:2e6}},B:{m:[['2026-01',30]],r:{return60:6,maxDrawdown:-22,medianValue30:2e6}},C:{m:[['2026-01',20]],r:{return60:-30,maxDrawdown:-60,medianValue30:2e6}}},symbol:'A',monthlyBudget:3500})"
        result = run_domain(expression)
        self.assertEqual([item["symbol"] for item in result], ["B", "C"])

    def test_outcome_timeline_starts_after_drawdown_not_initial_purchase(self):
        expression = "d.analyzeOutcomeTimeline({points:[{period:0,price:10,invested:1000,value:1000},{period:1,price:8,invested:2000,value:1600},{period:2,price:9,invested:3000,value:2700},{period:3,price:10,invested:3000,value:3300},{period:4,price:11,invested:3000,value:3600}],periodsPerMonth:1,buyPeriods:2,startPrice:10,declineEndPeriod:1})"
        result = run_domain(expression)
        self.assertEqual(result["buyCompleteMonth"], 2)
        self.assertEqual(result["breakEvenMonth"], 3)
        self.assertEqual(result["sustainedProfitMonth"], 3)
        self.assertEqual(result["returnToStartMonth"], 3)
        self.assertEqual(result["monthsAfterBuyingToBreakEven"], 1)

    def test_price_path_models_keep_required_endpoints(self):
        cycle = run_domain("d.buildPricePath({model:'cycle',current:100,bottom:70,target:110,steps:12,downSteps:4})")
        recent = run_domain("d.buildPricePath({model:'recent3m',current:100,bottom:70,target:100,steps:12,downSteps:4,recentPrices:[10,10.2,9.8,10.4,10,9.7,10.1,10.5,10.2,10.6]})")
        self.assertEqual(cycle["prices"][0], 100)
        self.assertEqual(cycle["prices"][4], 70)
        self.assertEqual(cycle["prices"][-1], 110)
        self.assertEqual(recent["modelUsed"], "recent3m")
        self.assertEqual(recent["sourcePoints"], 10)

    def test_recent_path_falls_back_when_cloud_payload_is_old(self):
        result = run_domain("d.buildPricePath({model:'recent3m',current:100,bottom:80,target:100,steps:6,downSteps:3,recentPrices:[]})")
        self.assertEqual(result["modelUsed"], "linear")
        self.assertEqual(result["fallbackReason"], "recent-data-unavailable")

    def test_presets_keep_market_assumptions_separate(self):
        presets = run_domain("d.SCENARIO_PRESETS")
        self.assertTrue(presets["cycle"]["useCycleReference"])
        self.assertIsNone(presets["cycle"]["drawdownPercent"])
        self.assertEqual(presets["correction"]["drawdownPercent"], 25)
        self.assertEqual(presets["crisis"]["recoveryMode"], "none")


if __name__ == "__main__":
    unittest.main()
