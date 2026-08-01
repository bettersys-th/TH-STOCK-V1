"""Optional independent end-of-day price validation providers.

Providers are activated only when their API key environment variable exists.
They never mutate the price store; results are written to the quality report.
"""

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _get_json(url, headers=None, timeout=30):
    request = Request(url, headers={"User-Agent": "TH-Stock-Toolkit/1.0", **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _comparison(symbol, local, external, source, external_date=None):
    diff_pct = (external / local - 1) * 100 if local else None
    return {
        "ticker": symbol, "source": source, "local": round(local, 4),
        "external": round(external, 4), "externalDate": external_date,
        "diffPct": round(diff_pct, 3) if diff_pct is not None else None,
        "match": diff_pct is not None and abs(diff_pct) <= 0.5,
    }


def check_twelve_data(latest_prices, symbols):
    key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    result = {"source": "Twelve Data (XBKK)", "configured": bool(key), "comparisons": [], "errors": []}
    if not key:
        return result
    for symbol in symbols:
        try:
            query = urlencode({"symbol": symbol, "interval": "1day", "mic_code": "XBKK",
                               "outputsize": 1, "adjust": "none", "apikey": key})
            payload = _get_json("https://api.twelvedata.com/time_series?" + query)
            values = payload.get("values") or []
            if not values:
                raise ValueError(payload.get("message", "no values"))
            row = values[0]
            result["comparisons"].append(_comparison(
                symbol, latest_prices[symbol], float(row["close"]), "twelve_data", row.get("datetime")))
        except Exception as exc:
            result["errors"].append({"ticker": symbol, "error": str(exc)[:180]})
    return result


def check_set_marketplace(latest_prices, symbols):
    """Cross-check official SET delayed quotation API when SET_API_KEY is set."""
    key = os.environ.get("SET_API_KEY", "").strip()
    result = {"source": "SET SMART Marketplace", "configured": bool(key), "comparisons": [], "errors": []}
    if not key:
        return result
    try:
        query = urlencode({"market": "SET,mai"})
        payload = _get_json("https://marketplace.set.or.th/api/public/delay-data/stock?" + query,
                            headers={"api-key": key})
        rows = payload if isinstance(payload, list) else payload.get("data", payload.get("stock", []))
        by_symbol = {str(row.get("symbol", "")).upper(): row for row in rows}
        for symbol in symbols:
            try:
                row = by_symbol[symbol]
                external = row.get("last") or row.get("close") or row.get("prior")
                if external is None:
                    raise ValueError("quotation has no last/close/prior")
                result["comparisons"].append(_comparison(
                    symbol, latest_prices[symbol], float(external), "set_marketplace",
                    row.get("time") or row.get("tradeDate")))
            except Exception as exc:
                result["errors"].append({"ticker": symbol, "error": str(exc)[:180]})
    except Exception as exc:
        result["errors"].append({"ticker": "*", "error": str(exc)[:180]})
    return result


def cross_check(prices, symbols):
    available = [s for s in symbols if s in prices and prices[s].get("c")]
    latest = {s: float(prices[s]["c"][-1]) for s in available}
    checks = [check_set_marketplace(latest, available), check_twelve_data(latest, available)]
    comparisons = [item for check in checks for item in check["comparisons"]]
    errors = [item for check in checks for item in check["errors"]]
    mismatches = [item for item in comparisons if not item["match"]]
    return {"providers": checks, "comparisonCount": len(comparisons),
            "mismatchCount": len(mismatches), "errorCount": len(errors),
            "mismatches": mismatches}
