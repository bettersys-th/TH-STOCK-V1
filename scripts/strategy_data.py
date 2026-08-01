"""Derived datasets for end-of-day Swing Trade and DCA tools."""

from collections import defaultdict
from datetime import datetime
from statistics import median

from accumulation import split_adjust


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def build_swing_signals(prices, splits, tickers, active_window_days=60):
    max_date = max((x["d"][-1] for x in prices.values() if x.get("d")), default=0)
    max_dt = datetime.strptime(str(max_date), "%Y%m%d") if max_date else None
    rows = []
    for ticker in tickers:
        raw = prices.get(ticker)
        if not raw or len(raw.get("d", [])) < 205:
            continue
        dates = raw["d"]
        last_dt = datetime.strptime(str(dates[-1]), "%Y%m%d")
        if max_dt and (max_dt - last_dt).days > active_window_days:
            continue
        events = [(int(e["date"].replace("-", "")), float(e["ratio"])) for e in splits.get(ticker, [])]
        close, volume = split_adjust(dates, raw["c"], raw.get("v") or [0] * len(dates), events)
        current = close[-1]
        ma20, ma50, ma200 = _mean(close[-20:]), _mean(close[-50:]), _mean(close[-200:])
        prior_high20, prior_high60 = max(close[-21:-1]), max(close[-61:-1])
        low20 = min(close[-20:])
        avg_vol20, avg_vol60 = _mean(volume[-20:]), _mean(volume[-60:])
        vol_ratio = avg_vol20 / avg_vol60 if avg_vol60 else 0
        value20 = median([p * v for p, v in zip(close[-20:], volume[-20:])])
        momentum20 = current / close[-21] - 1
        momentum60 = current / close[-61] - 1
        distance_breakout = current / prior_high20 - 1
        stop = low20
        risk = current - stop
        historical_target = max(prior_high60, max(close[-252:]))
        measured_target = current + max(0, prior_high20 - low20)
        target = max(historical_target, measured_target)
        reward = target - current
        rr = reward / risk if risk > 0 else 0

        score = 0
        score += 20 if current > ma20 else 0
        score += 15 if ma20 > ma50 else 0
        score += 15 if ma50 > ma200 else 0
        score += 15 if distance_breakout >= 0 else max(0, 15 * (distance_breakout + .08) / .08)
        score += min(15, max(0, (vol_ratio - .8) / .7 * 15))
        score += min(10, max(0, (momentum20 + .03) / .13 * 10))
        score += min(10, max(0, rr / 2 * 10))
        score = round(min(100, score))

        if value20 < 1_000_000:
            status = "illiquid"
        elif current < ma50 or momentum20 < -.08:
            status = "failed"
        elif current / ma20 - 1 > .12:
            status = "extended"
        elif distance_breakout >= 0 and vol_ratio >= 1.15 and ma20 > ma50:
            status = "triggered"
        elif current > ma20 and ma20 > ma50 and distance_breakout >= -.05:
            status = "setup"
        else:
            status = "neutral"

        reasons = []
        if current > ma20 > ma50: reasons.append("ราคาเหนือ MA20 และ MA50")
        if distance_breakout >= 0: reasons.append("ทะลุกรอบสูงสุด 20 วัน")
        elif distance_breakout >= -.05: reasons.append("ใกล้จุด breakout 20 วัน")
        if vol_ratio >= 1.15: reasons.append(f"Volume 20/60 วัน {vol_ratio:.1f}x")
        if momentum20 > 0: reasons.append(f"Momentum 20 วัน +{momentum20*100:.1f}%")
        rows.append({
            "t": ticker, "date": f"{str(dates[-1])[:4]}-{str(dates[-1])[4:6]}-{str(dates[-1])[6:8]}",
            "price": round(current, 3), "status": status, "score": score,
            "ma20": round(ma20, 3), "ma50": round(ma50, 3), "ma200": round(ma200, 3),
            "breakoutPct": round(distance_breakout * 100, 2), "volumeRatio": round(vol_ratio, 2),
            "momentum20": round(momentum20 * 100, 2), "momentum60": round(momentum60 * 100, 2),
            "stop": round(stop, 3), "target": round(target, 3), "rr": round(rr, 2),
            "medianValue20": round(value20), "reasons": reasons[:4],
        })
    rank = {"triggered": 0, "setup": 1, "extended": 2, "failed": 3, "neutral": 4, "illiquid": 5}
    rows.sort(key=lambda x: (rank[x["status"]], -x["score"], x["t"]))
    return rows


def build_dca_compact(prices, splits, dividends, tickers):
    out = {}
    for ticker in tickers:
        raw = prices.get(ticker)
        if not raw or len(raw.get("d", [])) < 30:
            continue
        dates = raw["d"]
        events = [(int(e["date"].replace("-", "")), float(e["ratio"])) for e in splits.get(ticker, [])]
        close, _ = split_adjust(dates, raw["c"], raw.get("v") or [0] * len(dates), events)
        monthly = {}
        for d, price in zip(dates, close):
            monthly[str(d)[:6]] = round(price, 4)  # last trading close in month
        if len(monthly) < 12:
            continue
        div_by_month = defaultdict(float)
        for event in dividends.get(ticker, []):
            event_date = int(event["date"].replace("-", ""))
            factor = 1.0
            for split_date, ratio in events:
                if split_date > event_date:
                    factor *= ratio
            div_by_month[str(event_date)[:6]] += float(event["amount"]) / factor
        monthly_items = sorted(monthly.items())[-240:]  # 20 years keeps the static page practical
        first_month = monthly_items[0][0]
        out[ticker] = {
            "m": [[f"{month[:4]}-{month[4:]}", price] for month, price in monthly_items],
            "dv": [[f"{month[:4]}-{month[4:]}", round(amount, 5)] for month, amount in sorted(div_by_month.items()) if amount and month >= first_month],
        }
    return out
