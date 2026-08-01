#!/usr/bin/env python3
"""Walk-forward diagnostic for the point-in-time accumulation score.

This is intentionally a research report, not an optimizer. Signals are sampled
every 20 trading days to reduce overlap and evaluated without looking forward
when creating the score.
"""

import argparse
import gzip
import json
import os
from collections import defaultdict
from datetime import datetime
from statistics import mean, median

from accumulation import MIN_HISTORY, score_at, split_adjust

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def percentile(values, q):
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * q)]


def summarize(values):
    if not values:
        return {"n": 0}
    return {
        "n": len(values), "meanPct": round(mean(values) * 100, 2),
        "medianPct": round(median(values) * 100, 2),
        "positivePct": round(sum(x > 0 for x in values) / len(values) * 100, 1),
        "p10Pct": round(percentile(values, .10) * 100, 2),
        "p90Pct": round(percentile(values, .90) * 100, 2),
    }


def run(start_year=2016, step=20):
    with gzip.open(os.path.join(ROOT, "data", "prices.json.gz"), "rt", encoding="utf-8") as f:
        prices = json.load(f)
    with open(os.path.join(ROOT, "data", "splits.json"), encoding="utf-8") as f:
        splits = json.load(f)

    outcomes = defaultdict(list)
    for ticker, raw in prices.items():
        dates = raw.get("d", [])
        if len(dates) <= MIN_HISTORY + 120:
            continue
        events = [(int(e["date"].replace("-", "")), float(e["ratio"])) for e in splits.get(ticker, [])]
        close, volume = split_adjust(dates, raw["c"], raw.get("v") or [0] * len(dates), events)
        first = next((i for i, d in enumerate(dates) if int(str(d)[:4]) >= start_year), MIN_HISTORY)
        for idx in range(max(MIN_HISTORY, first), len(dates) - 120, step):
            signal = score_at(dates, close, volume, idx)
            if not signal:
                continue
            for horizon in (20, 60, 120):
                ret = close[idx + horizon] / close[idx] - 1
                outcomes[(signal["status"], horizon)].append(ret)
                bucket = "score70+" if signal["score"] >= 70 else "score60-69" if signal["score"] >= 60 else "score50-59" if signal["score"] >= 50 else "score<50"
                outcomes[(bucket, horizon)].append(ret)

    report = {
        "method": "Point-in-time, current ticker universe, sampled every %d trading days; price return excludes fees/dividends" % step,
        "startYear": start_year, "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "results": {f"{group}_{horizon}d": summarize(values)
                    for (group, horizon), values in sorted(outcomes.items())}
    }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--step", type=int, default=20)
    parser.add_argument("--output", default=os.path.join(ROOT, "data", "accumulation_backtest.json"))
    args = parser.parse_args()
    result = run(args.start_year, args.step)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
