#!/usr/bin/env python3
"""Point-in-time walk-forward diagnostic for Swing signals."""

import argparse
import gzip
import json
import os
from collections import defaultdict
from datetime import datetime
from statistics import mean, median

from accumulation import split_adjust
from strategy_data import swing_signal_at

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def summarize(rows):
    if not rows:
        return {"n": 0}
    returns = [x[0] for x in rows]
    maes = [x[1] for x in rows]
    return {"n": len(rows), "meanPct": round(mean(returns) * 100, 2),
            "medianPct": round(median(returns) * 100, 2),
            "positivePct": round(sum(x > 0 for x in returns) / len(rows) * 100, 1),
            "meanMaePct": round(mean(maes) * 100, 2)}


def run(start_year=2016, step=20):
    with gzip.open(os.path.join(ROOT, "data", "prices.json.gz"), "rt", encoding="utf-8") as f:
        prices = json.load(f)
    with open(os.path.join(ROOT, "data", "splits.json"), encoding="utf-8") as f:
        splits = json.load(f)
    outcomes = defaultdict(list)
    resolution = defaultdict(lambda: {"targetFirst": 0, "stopFirst": 0, "neither": 0})
    for ticker, raw in prices.items():
        dates = raw.get("d", [])
        if len(dates) < 325:
            continue
        events = [(int(e["date"].replace("-", "")), float(e["ratio"])) for e in splits.get(ticker, [])]
        close, volume = split_adjust(dates, raw["c"], raw.get("v") or [0] * len(dates), events)
        first = next((i for i, d in enumerate(dates) if int(str(d)[:4]) >= start_year), 204)
        for idx in range(max(204, first), len(dates) - 60, step):
            signal = swing_signal_at(ticker, dates, close, volume, idx)
            if not signal:
                continue
            bucket = "score70+" if signal["score"] >= 70 else "score60-69" if signal["score"] >= 60 else "score50-59" if signal["score"] >= 50 else "score<50"
            for horizon in (10, 20, 60):
                future = close[idx + 1:idx + horizon + 1]
                ret = close[idx + horizon] / close[idx] - 1
                mae = min(future) / close[idx] - 1
                outcomes[(signal["status"], horizon)].append((ret, mae))
                outcomes[(bucket, horizon)].append((ret, mae))
            if signal["status"] in ("triggered", "setup"):
                result = "neither"
                for price in close[idx + 1:idx + 61]:
                    # Daily close data cannot resolve intraday ordering; stop wins ties.
                    if price <= signal["stop"]:
                        result = "stopFirst"; break
                    if price >= signal["target"]:
                        result = "targetFirst"; break
                resolution[signal["status"]][result] += 1
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"), "startYear": start_year,
        "sampleStepTradingDays": step,
        "limitations": "Current ticker universe (survivorship bias), close-only target/stop, excludes fees/dividends/slippage",
        "results": {f"{group}_{horizon}d": summarize(rows)
                    for (group, horizon), rows in sorted(outcomes.items())},
        "targetStop60d": dict(resolution),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--step", type=int, default=20)
    parser.add_argument("--output", default=os.path.join(ROOT, "data", "swing_backtest.json"))
    args = parser.parse_args()
    report = run(args.start_year, args.step)
    tmp = args.output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
