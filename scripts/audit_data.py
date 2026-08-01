#!/usr/bin/env python3
"""Audit the existing local store without downloading or mutating market bars."""

import gzip
import json
import os
from collections import Counter
from datetime import datetime

from market_validation import cross_check

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")


def load_json(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run():
    with gzip.open(os.path.join(DATA, "prices.json.gz"), "rt", encoding="utf-8") as f:
        prices = json.load(f)
    with open(os.path.join(DATA, "clean_tickers.txt"), encoding="utf-8") as f:
        tickers = [line.strip() for line in f if line.strip()]
    splits, dividends = load_json("splits.json", {}), load_json("dividends.json", {})
    max_date = max((x["d"][-1] for x in prices.values() if x.get("d")), default=None)
    max_dt = datetime.strptime(str(max_date), "%Y%m%d") if max_date else None
    stale = Counter()
    malformed = []
    ranked = []
    for ticker in tickers:
        raw = prices.get(ticker)
        if not raw or not raw.get("d"):
            stale["missing"] += 1
            continue
        if len(raw["d"]) != len(raw.get("c", [])) or len(raw["d"]) != len(raw.get("v", [])) or len(raw["d"]) != len(set(raw["d"])):
            malformed.append(ticker)
        lag = (max_dt - datetime.strptime(str(raw["d"][-1]), "%Y%m%d")).days
        stale["current"] += lag <= 1
        stale["2to7Days"] += 2 <= lag <= 7
        stale["8to60Days"] += 8 <= lag <= 60
        stale["over60Days"] += lag > 60
        ranked.append((float(raw["c"][-1]) * float(raw["v"][-1]), ticker))
    sample = [ticker for _, ticker in sorted(ranked, reverse=True)[:20]]
    validation = cross_check(prices, sample)
    return {
        "mode": "offline_audit", "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": "warning" if malformed or validation["mismatchCount"] or validation["errorCount"] else ("ok" if validation["comparisonCount"] else "unverified"),
        "configuredTickers": len(tickers), "priceTickers": len(prices),
        "latestDate": f"{str(max_date)[:4]}-{str(max_date)[4:6]}-{str(max_date)[6:8]}" if max_date else None,
        "freshness": dict(stale), "malformedTickers": malformed,
        "splitTickers": len(splits), "splitEvents": sum(map(len, splits.values())),
        "dividendTickers": len(dividends), "dividendEvents": sum(map(len, dividends.values())),
        "crossCheck": validation,
    }


if __name__ == "__main__":
    report = run()
    path = os.path.join(DATA, "data_quality.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
