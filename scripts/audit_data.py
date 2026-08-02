#!/usr/bin/env python3
"""Audit the existing local store without downloading or mutating market bars."""

import gzip
import json
import os
import csv
from collections import Counter
from datetime import datetime, timedelta

from market_validation import cross_check

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")


def load_json(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_price_coverage(prices, tickers, max_date):
    """Find recent gaps using dates observed across the active market, not weekdays."""
    if not max_date:
        return {"summary": {}, "tickers": []}
    max_dt = datetime.strptime(str(max_date), "%Y%m%d")
    cutoff = int((max_dt - timedelta(days=365)).strftime("%Y%m%d"))
    active = {ticker: prices[ticker] for ticker in tickers
              if ticker in prices and prices[ticker].get("d")
              and (max_dt - datetime.strptime(str(prices[ticker]["d"][-1]), "%Y%m%d")).days <= 60}
    date_counts = Counter(d for raw in active.values() for d in raw["d"] if d >= cutoff)
    reference_threshold = max(10, int(len(active) * .25))
    market_dates = sorted(d for d, count in date_counts.items() if count >= reference_threshold)
    rows, status_counts = [], Counter()
    for ticker in tickers:
        raw = prices.get(ticker)
        if not raw or not raw.get("d"):
            rows.append({"ticker": ticker, "status": "missing", "firstDate": None, "lastDate": None,
                         "bars": 0, "lagDays": None, "missingRecentCount": 0,
                         "missingRecentDates": [], "ohlcLast5Complete": False})
            status_counts["missing"] += 1
            continue
        dates, closes, volumes = raw["d"], raw.get("c", []), raw.get("v", [])
        malformed = len(dates) != len(closes) or len(dates) != len(volumes) or len(dates) != len(set(dates))
        lag = (max_dt - datetime.strptime(str(dates[-1]), "%Y%m%d")).days
        date_set = set(dates)
        start = max(cutoff, dates[0])
        missing_dates = [d for d in market_dates if start <= d <= dates[-1] and d not in date_set]
        o, h, lo = raw.get("o", []), raw.get("h", []), raw.get("lo", [])
        recent_indexes = range(max(0, len(dates) - 5), len(dates))
        ohlc_complete = len(dates) >= 5 and all(
            i < len(o) and i < len(h) and i < len(lo)
            and o[i] is not None and h[i] is not None and lo[i] is not None
            for i in recent_indexes
        )
        status = ("malformed" if malformed else "stale" if lag > 7 else
                  "gaps" if missing_dates else "ok")
        status_counts[status] += 1
        rows.append({
            "ticker": ticker, "status": status,
            "firstDate": str(dates[0]), "lastDate": str(dates[-1]), "bars": len(dates),
            "lagDays": lag, "missingRecentCount": len(missing_dates),
            "missingRecentDates": [str(d) for d in missing_dates[-30:]],
            "ohlcLast5Complete": ohlc_complete,
        })
    rows.sort(key=lambda row: ({"missing": 0, "malformed": 1, "stale": 2, "gaps": 3, "ok": 4}[row["status"]],
                               -(row["missingRecentCount"] or 0), row["ticker"]))
    return {
        "summary": {"referenceMarketDays": len(market_dates), "activeTickers": len(active),
                    "referenceThreshold": reference_threshold, "lookbackDays": 365,
                    "statusCounts": dict(status_counts),
                    "ohlcLast5Complete": sum(row["ohlcLast5Complete"] for row in rows)},
        "tickers": rows,
    }


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
    coverage = build_price_coverage(prices, tickers, max_date)
    return {
        "mode": "offline_audit", "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": "warning" if malformed or validation["mismatchCount"] or validation["errorCount"] else ("ok" if validation["comparisonCount"] else "unverified"),
        "configuredTickers": len(tickers), "priceTickers": len(prices),
        "latestDate": f"{str(max_date)[:4]}-{str(max_date)[4:6]}-{str(max_date)[6:8]}" if max_date else None,
        "freshness": dict(stale), "malformedTickers": malformed,
        "splitTickers": len(splits), "splitEvents": sum(map(len, splits.values())),
        "dividendTickers": len(dividends), "dividendEvents": sum(map(len, dividends.values())),
        "crossCheck": validation,
        "priceCoverage": coverage["summary"],
        "priceCoverageTickers": coverage["tickers"],
    }


if __name__ == "__main__":
    report = run()
    path = os.path.join(DATA, "data_quality.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    coverage_path = os.path.join(DATA, "price_coverage.csv")
    with open(coverage_path + ".tmp", "w", encoding="utf-8-sig", newline="") as f:
        fields = ["ticker", "status", "firstDate", "lastDate", "bars", "lagDays",
                  "missingRecentCount", "ohlcLast5Complete", "missingRecentDates"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in report.pop("priceCoverageTickers"):
            item = dict(row)
            item["missingRecentDates"] = " ".join(item["missingRecentDates"])
            writer.writerow(item)
    os.replace(coverage_path + ".tmp", coverage_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"coverage CSV: {coverage_path}")
