"""Point-in-time accumulation scoring from daily close and volume only.

Every feature at index ``idx`` uses data at or before that index.  The module
is deliberately dependency-free so the daily GitHub Action can run it without
adding a numerical stack.
"""

from math import sqrt
from statistics import median

MIN_HISTORY = 260
MIN_MEDIAN_VALUE = 1_000_000  # THB/day, avoids obviously untradeable names
VERY_LOW_VALUE = 1_000_000    # warning when every one of 30 sessions is below this


def split_adjust(dates, closes, volumes, split_events):
    """Return split-comparable close and share volume series.

    ``split_events`` contains ``(YYYYMMDD, ratio)``. Historical price is divided
    and historical share volume is multiplied by later split ratios.
    """
    prices, vols = [], []
    for d, c, v in zip(dates, closes, volumes):
        factor = 1.0
        for split_date, ratio in split_events:
            if split_date > d:
                factor *= ratio
        prices.append(float(c) / factor)
        vols.append(float(v) * factor)
    return prices, vols


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _stdev(values):
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return sqrt(sum((x - avg) ** 2 for x in values) / len(values))


def _returns(values):
    return [values[i] / values[i - 1] - 1 for i in range(1, len(values))
            if values[i - 1] > 0]


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def score_at(dates, closes, volumes, idx=None):
    """Score one ticker at ``idx`` using only information known by that date."""
    if idx is None:
        idx = len(closes) - 1
    if idx < MIN_HISTORY or idx >= len(closes):
        return None

    p = closes[:idx + 1]
    v = volumes[:idx + 1]
    current = p[-1]
    if current <= 0:
        return None

    p20, p30, p60, p252 = p[-20:], p[-30:], p[-60:], p[-252:]
    v20, v40 = v[-20:], v[-40:]
    v30 = v[-30:]
    value20 = [price * volume for price, volume in zip(p20, v20)]
    value30 = [price * volume for price, volume in zip(p30, v30)]
    median_value = median(value20)
    median_value30 = median(value30)
    average_volume30 = _mean(v30)
    average_volume5 = _mean(v[-5:])
    prior_volume20 = _mean(v[-25:-5])
    volume5_ratio = average_volume5 / prior_volume20 if prior_volume20 > 0 else 0.0
    average_value5 = _mean([price * volume for price, volume in zip(p[-5:], v[-5:])])
    low_value_30_straight = len(value30) == 30 and all(value < VERY_LOW_VALUE for value in value30)

    high252 = max(p252)
    low20 = min(p20)
    prior_low20 = min(p[-21:-1])
    prior_high20 = max(p[-21:-1])
    drawdown = current / high252 - 1
    range20 = (max(p20) - min(p20)) / min(p20) if min(p20) > 0 else 9
    range60 = (max(p60) - min(p60)) / min(p60) if min(p60) > 0 else 9
    vol20 = _stdev(_returns(p[-21:]))
    vol60 = _stdev(_returns(p[-61:]))

    # Setup (40): meaningful drawdown, then contraction and base formation.
    drawdown_points = 0
    if drawdown <= -0.15:
        drawdown_points = 14 * _clamp((-drawdown - 0.15) / 0.20)
        if drawdown < -0.55:
            drawdown_points *= _clamp((0.80 + drawdown) / 0.25)
    tight_points = 10 * _clamp((0.18 - range20) / 0.10)
    contraction_points = 8 * _clamp((range60 * 0.75 - range20) / max(range60 * 0.35, 0.01))
    volatility_points = 8 * _clamp((vol60 - vol20) / max(vol60 * 0.5, 0.005))
    setup = round(drawdown_points + tight_points + contraction_points + volatility_points)

    # Demand evidence (30): up-day volume dominance and price resilience.
    up_volume = sum(v20[i] for i in range(1, 20) if p20[i] > p20[i - 1])
    down_volume = sum(v20[i] for i in range(1, 20) if p20[i] < p20[i - 1])
    demand_ratio = up_volume / down_volume if down_volume > 0 else (2.0 if up_volume else 0.0)
    demand_points = 14 * _clamp((demand_ratio - 0.8) / 0.8)
    higher_low_points = 8 * _clamp((current / low20 - 1) / 0.08)
    recent_volume = _mean(v[-10:])
    earlier_volume = _mean(v[-40:-20])
    volume_confirm_points = 8 * _clamp((recent_volume / earlier_volume - 0.9) / 0.6) if earlier_volume else 0
    demand = round(demand_points + higher_low_points + volume_confirm_points)

    # Confirmation (30): trend has stopped falling and price challenges its base.
    sma20 = _mean(p20)
    sma20_5_days_ago = _mean(p[-25:-5])
    above_ma_points = 10 * _clamp((current / sma20 - 0.99) / 0.04)
    slope_points = 8 * _clamp((sma20 / sma20_5_days_ago - 0.995) / 0.02) if sma20_5_days_ago else 0
    breakout_points = 8 * _clamp((current / prior_high20 - 0.94) / 0.06) if prior_high20 else 0
    momentum5 = current / p[-6] - 1
    momentum20 = current / p[-21] - 1
    momentum_points = 4 * _clamp((momentum5 + 0.01) / 0.05)
    confirmation = round(above_ma_points + slope_points + breakout_points + momentum_points)

    liquid = median_value >= MIN_MEDIAN_VALUE
    invalidated = current < prior_low20 * 0.98
    total = min(100, setup + demand + confirmation)
    if not liquid:
        status = "illiquid"
    elif invalidated:
        status = "invalidated"
    elif total >= 62 and confirmation >= 18 and setup >= 18:
        status = "confirmed"
    elif total >= 45 and setup >= 18:
        status = "building"
    elif drawdown <= -0.15 and setup >= 10:
        status = "watch"
    else:
        status = "neutral"

    reasons = []
    if drawdown <= -0.15:
        reasons.append(f"ต่ำกว่ายอด 52 สัปดาห์ {abs(drawdown) * 100:.0f}%")
    if range20 <= 0.12:
        reasons.append(f"กรอบ 20 วันแคบ {range20 * 100:.1f}%")
    if vol20 < vol60 * 0.8:
        reasons.append("ความผันผวนกำลังลดลง")
    if demand_ratio >= 1.2:
        reasons.append(f"Up-volume/Down-volume {demand_ratio:.1f}x")
    if volume5_ratio >= 1.3:
        reasons.append(f"Volume 5 วันเร่งขึ้น {volume5_ratio:.1f}x")
    if current > sma20 and sma20 > sma20_5_days_ago:
        reasons.append("ราคาเหนือ MA20 และเส้นเริ่มชันขึ้น")
    if invalidated:
        reasons.append("ราคาหลุดฐาน 20 วัน")
    if not liquid:
        reasons.append("มูลค่าซื้อขายต่ำกว่าเกณฑ์")
    if low_value_30_straight:
        reasons.append("มูลค่าซื้อขายต่ำมากต่อเนื่อง 30 วัน")

    return {
        "date": str(dates[idx]), "price": round(current, 3), "score": total,
        "status": status, "setup": setup, "demand": demand,
        "confirmation": confirmation, "drawdown52": round(drawdown * 100, 2),
        "range20": round(range20 * 100, 2), "demandRatio": round(demand_ratio, 2),
        "medianValue20": round(median_value), "medianValue30": round(median_value30),
        "avgVolume30": round(average_volume30), "lowLiquidity30": low_value_30_straight,
        "avgVolume5": round(average_volume5), "avgValue5": round(average_value5),
        "volume5Ratio": round(volume5_ratio, 2),
        "momentum5": round(momentum5 * 100, 2), "momentum20": round(momentum20 * 100, 2),
        "reasons": reasons[:5]
    }


def build_signals(prices, splits, tickers, active_window_days=60):
    """Build latest point-in-time signals for the scanner."""
    signals = []
    max_date = max((x["d"][-1] for x in prices.values() if x.get("d")), default=0)
    from datetime import datetime
    max_dt = datetime.strptime(str(max_date), "%Y%m%d") if max_date else None
    for ticker in tickers:
        raw = prices.get(ticker)
        if not raw or len(raw.get("d", [])) <= MIN_HISTORY:
            continue
        dates = raw["d"]
        latest_dt = datetime.strptime(str(dates[-1]), "%Y%m%d")
        if max_dt and (max_dt - latest_dt).days > active_window_days:
            continue
        split_events = [(int(e["date"].replace("-", "")), float(e["ratio"]))
                        for e in splits.get(ticker, [])]
        volumes = raw.get("v") or [0] * len(dates)
        adj_close, adj_volume = split_adjust(dates, raw["c"], volumes, split_events)
        signal = score_at(dates, adj_close, adj_volume)
        if signal:
            signal["t"] = ticker
            signal["date"] = f'{signal["date"][:4]}-{signal["date"][4:6]}-{signal["date"][6:8]}'
            signals.append(signal)
    rank = {"confirmed": 0, "building": 1, "watch": 2, "invalidated": 3,
            "neutral": 4, "illiquid": 5}
    signals.sort(key=lambda s: (rank[s["status"]], -s["score"], s["t"]))
    return signals
