#!/usr/bin/env python3
"""
update_and_build.py
====================
สคริปต์เดียวที่ทำทุกอย่าง สำหรับรันผ่าน GitHub Actions ทุกวัน:

  1. โหลด data/prices.json.gz (ราคารายวันดิบ = source of truth สะสมมาเรื่อยๆ)
  2. ดึงราคาล่าสุด + split + ปันผล จาก Yahoo Finance (yfinance) มา "ต่อ" ของเดิม
  3. คำนวณใหม่ทั้งหมด: ราคาสิ้นปี, cycle (zigzag 20%), รายชื่อหุ้นขาลงตอนนี้
  4. Build ไฟล์ stock_toolkit.html ใหม่ทั้งไฟล์
  5. เขียนทับไฟล์ทั้งหมดใน data/ และ stock_toolkit.html
     (GitHub Actions เป็นคน commit/push ต่อ ไม่ใช่สคริปต์นี้)

รันเอง (local):
    pip install yfinance --upgrade
    python scripts/update_and_build.py

ตัวแปรปรับได้ด้านล่าง: TICKERS, ZIGZAG_PCT, ACTIVE_WINDOW_DAYS
"""

import gzip
import json
import os
import sys
import tempfile
import time
from datetime import datetime, date, timedelta
from accumulation import build_signals
from market_validation import cross_check

try:
    import yfinance as yf
except ImportError:
    print("ต้องติดตั้ง yfinance ก่อน: pip install yfinance --upgrade")
    sys.exit(1)

if hasattr(yf, "set_tz_cache_location"):
    yf_cache = os.environ.get("YFINANCE_CACHE_DIR") or os.path.join(tempfile.gettempdir(), "th-stock-yfinance")
    os.makedirs(yf_cache, exist_ok=True)
    yf.set_tz_cache_location(yf_cache)

# -----------------------------------------------------------------------
# ค่าคงที่ / path
# -----------------------------------------------------------------------
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PRICES_GZ = os.path.join(DATA_DIR, "prices.json.gz")
TICKERS_FILE = os.path.join(DATA_DIR, "clean_tickers.txt")
OUTPUT_HTML = os.path.join(os.path.dirname(__file__), "..", "index.html")

ZIGZAG_PCT = 0.20            # นิยาม cycle: ขึ้น/ลงอย่างน้อย 20%
ACTIVE_WINDOW_DAYS = 60      # ถือว่า "ยังเทรดอยู่" ถ้ามีข้อมูลใน 60 วันล่าสุด
SLEEP_SECONDS = 1.0          # หน่วงระหว่าง ticker กัน Yahoo rate-limit
REPAIR_OVERLAP_DAYS = 30     # ดึงทับช่วงเดิมเพื่อรับ correction จากผู้ให้บริการ
STALE_REPAIR_PERIOD = "1y"   # พยายามซ่อมหุ้นที่ข้อมูลเก่ากว่าช่วง active
CROSS_CHECK_LIMIT = int(os.environ.get("CROSS_CHECK_LIMIT", "8"))  # จำกัด API credits
MIN_ACTIVE_FETCH_SUCCESS = 0.80

# --- นิยาม "ช่วงสะสม/ทยอยขาย" (ราคานิ่ง + volume เพิ่มขึ้นเรื่อยๆ ก่อนจุดกลับตัว) ---
# ทดลองสแกนหน้าต่างเวลาหลายขนาดก่อนถึงจุด peak/trough แต่ละจุด เลือกขนาดที่ใหญ่ที่สุด
# ที่ยัง (ก) ราคาไม่วิ่งเกิน QUIET_PRICE_RANGE_PCT ตลอดหน้าต่างนั้น และ (ข) volume เฉลี่ย
# ครึ่งหลังของหน้าต่าง >= ครึ่งแรก x VOL_RISE_RATIO — เป็นการประมาณแบบ heuristic ไม่ใช่
# สัญญาณที่พิสูจน์ทางสถิติ ปรับค่าได้ตามต้องการ
ACCUM_WINDOW_SIZES = [10, 20, 30, 40, 60, 80, 100, 120, 150, 180]
QUIET_PRICE_RANGE_PCT = 0.15   # ราคาสูงสุด-ต่ำสุดในหน้าต่างต้องไม่เกิน 15% ของราคาต่ำสุด
VOL_RISE_RATIO = 1.05          # volume เฉลี่ยครึ่งหลัง ต้อง >= ครึ่งแรก x 1.05


# -----------------------------------------------------------------------
# 1) โหลด/บันทึก prices.json.gz
# -----------------------------------------------------------------------
def load_prices():
    if not os.path.exists(PRICES_GZ):
        return {}
    with gzip.open(PRICES_GZ, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_prices(prices):
    raw = json.dumps(prices, separators=(",", ":"))
    tmp_path = PRICES_GZ + ".tmp"
    with gzip.open(tmp_path, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(raw)
    os.replace(tmp_path, PRICES_GZ)
    print(f"saved {PRICES_GZ} ({os.path.getsize(PRICES_GZ)/1e6:.1f} MB gzipped)")


def load_tickers():
    with open(TICKERS_FILE, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def read_json_file(name, default):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(name, value, pretty=False):
    path = os.path.join(DATA_DIR, name)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2 if pretty else None,
                  separators=None if pretty else (",", ":"))
    os.replace(tmp_path, path)


# -----------------------------------------------------------------------
# 2) ดึงข้อมูลใหม่จาก Yahoo Finance แล้ว "ต่อ" ของเดิม
# -----------------------------------------------------------------------
def update_prices(prices, tickers):
    n_updated = 0
    n_corrected = 0
    successful, empty, errors = [], [], []
    max_saved_date = max((x["d"][-1] for x in prices.values() if x.get("d")), default=None)
    max_saved_dt = datetime.strptime(str(max_saved_date), "%Y%m%d").date() if max_saved_date else None
    for i, t in enumerate(tickers, 1):
        try:
            entry = prices.get(t)
            kwargs = {"interval": "1d", "auto_adjust": False, "actions": False,
                      "repair": True, "keepna": False, "timeout": 20}
            if entry and entry.get("d") and max_saved_dt:
                last_dt = datetime.strptime(str(entry["d"][-1]), "%Y%m%d").date()
                if (max_saved_dt - last_dt).days <= ACTIVE_WINDOW_DAYS:
                    kwargs["start"] = (last_dt - timedelta(days=REPAIR_OVERLAP_DAYS)).isoformat()
                    kwargs["end"] = (date.today() + timedelta(days=1)).isoformat()
                else:
                    kwargs["period"] = STALE_REPAIR_PERIOD
            else:
                kwargs["period"] = STALE_REPAIR_PERIOD
            hist = yf.Ticker(f"{t}.BK").history(**kwargs)
            if hist.empty:
                empty.append(t)
                continue
            entry = prices.setdefault(t, {"d": [], "c": [], "v": []})
            entry.setdefault("v", [0] * len(entry["d"]))  # migrate เก่าไม่มี volume
            combined_c = dict(zip(entry["d"], entry["c"]))
            combined_v = dict(zip(entry["d"], entry["v"]))
            before_dates = set(entry["d"])
            changed_existing = False
            for idx, row in hist.iterrows():
                d_int = int(idx.strftime("%Y%m%d"))
                close = float(row["Close"])
                volume = int(row["Volume"]) if row["Volume"] == row["Volume"] else 0
                if not (close > 0) or volume <= 0:
                    continue
                rounded = round(close, 4)
                if d_int in combined_c and (combined_c[d_int] != rounded or combined_v.get(d_int) != volume):
                    changed_existing = True
                combined_c[d_int] = rounded
                combined_v[d_int] = volume
            if combined_c:
                all_dates = sorted(combined_c.keys())
                entry["d"] = all_dates
                entry["c"] = [combined_c[d] for d in all_dates]
                entry["v"] = [combined_v.get(d, 0) for d in all_dates]
            if set(entry["d"]) - before_dates:
                n_updated += 1
            if changed_existing:
                n_corrected += 1
            successful.append(t)
        except Exception as e:
            print(f"  [{i}/{len(tickers)}] {t}: fetch error ({e})")
            errors.append({"ticker": t, "error": str(e)[:180]})
        if i % 50 == 0:
            print(f"  ...{i}/{len(tickers)} tickers checked")
        time.sleep(SLEEP_SECONDS)
    print(f"prices: {n_updated} new bars | {n_corrected} corrected | {len(errors)} errors")
    report = {"success": successful, "empty": empty, "errors": errors,
              "newBarTickers": n_updated, "correctedTickers": n_corrected}
    return prices, report


def fetch_splits_dividends(tickers):
    """ดึง split + ปันผล ใหม่ทั้งหมดจาก Yahoo (ข้อมูลพวกนี้เบา ดึงใหม่ทุกครั้งง่ายกว่า diff)"""
    splits, dividends = {}, {}
    successful, errors = [], []
    for i, t in enumerate(tickers, 1):
        try:
            yft = yf.Ticker(f"{t}.BK")
            sp = yft.splits
            dv = yft.dividends
            if len(sp):
                splits[t] = [{"date": idx.strftime("%Y-%m-%d"), "ratio": float(v)} for idx, v in sp.items() if v and v != 1.0]
            if len(dv):
                dividends[t] = [{"date": idx.strftime("%Y-%m-%d"), "amount": float(v)} for idx, v in dv.items()]
            successful.append(t)
        except Exception as e:
            print(f"  [{i}/{len(tickers)}] {t}: splits/div fetch error ({e})")
            errors.append({"ticker": t, "error": str(e)[:180]})
        if i % 50 == 0:
            print(f"  ...{i}/{len(tickers)} tickers checked (splits/div)")
        time.sleep(SLEEP_SECONDS)
    return splits, dividends, {"success": successful, "errors": errors}


# -----------------------------------------------------------------------
# 3) คำนวณ derived data ทั้งหมด (เหมือนที่เคยทำแบบ manual มาก่อน)
# -----------------------------------------------------------------------
def sort_splits(splits_raw):
    """เก็บ split เป็น exact date ต่อครั้ง (ไม่ aggregate ตามปี) เพื่อให้คำนวณปันผลแม่นยำระดับวัน
    (กรณีมี split มากกว่า 1 ครั้งในปีเดียวกัน หรือปันผลจ่ายก่อน/หลัง split ในปีเดียวกัน)"""
    out = {}
    for t, evs in splits_raw.items():
        clean = [{"date": e["date"], "ratio": float(e["ratio"])} for e in evs if e.get("ratio") and e["ratio"] != 1.0]
        clean.sort(key=lambda e: e["date"])
        if clean:
            out[t] = clean
    return out


def sort_dividends(div_raw):
    """เก็บปันผลแบบ exact ex-date ต่อครั้ง (ไม่ sum รายปี) เพื่อให้ตรวจสอบกับข้อมูลจริงได้"""
    out = {}
    for t, evs in div_raw.items():
        clean = [{"date": e["date"], "amount": round(e["amount"], 4)} for e in evs if e.get("amount")]
        clean.sort(key=lambda e: e["date"])
        if clean:
            out[t] = clean
    return out


def merge_actions(existing, fetched, value_field):
    """Merge by ticker/date so a temporary provider failure never erases history."""
    merged = {}
    for ticker in set(existing) | set(fetched):
        by_date = {str(e["date"]): dict(e) for e in existing.get(ticker, []) if e.get("date")}
        for event in fetched.get(ticker, []):
            if event.get("date") and event.get(value_field) is not None:
                by_date[str(event["date"])] = dict(event)
        if by_date:
            merged[ticker] = [by_date[d] for d in sorted(by_date)]
    return merged


def validate_store(prices, tickers, price_report, action_report):
    """Return quality metrics and raise only when the active universe fetch collapses."""
    configured = set(tickers)
    present = configured & set(prices)
    max_date = max((x["d"][-1] for x in prices.values() if x.get("d")), default=None)
    active = set()
    if max_date:
        max_dt = datetime.strptime(str(max_date), "%Y%m%d")
        for ticker in present:
            raw = prices[ticker]
            if not raw.get("d"):
                continue
            last_dt = datetime.strptime(str(raw["d"][-1]), "%Y%m%d")
            if (max_dt - last_dt).days <= ACTIVE_WINDOW_DAYS:
                active.add(ticker)
    succeeded = set(price_report["success"])
    action_succeeded = set(action_report["success"])
    active_success_rate = len(active & succeeded) / len(active) if active else 0
    active_action_rate = len(active & action_succeeded) / len(active) if active else 0
    metrics = {
        "configuredTickers": len(configured), "priceTickers": len(present),
        "activeTickers": len(active), "latestDate": ymd_to_iso(max_date) if max_date else None,
        "activeFetchSuccessPct": round(active_success_rate * 100, 1),
        "activeActionFetchSuccessPct": round(active_action_rate * 100, 1),
        "priceFetchErrors": len(price_report["errors"]),
        "priceEmptyResponses": len(price_report["empty"]),
        "actionFetchErrors": len(action_report["errors"]),
    }
    if active and active_success_rate < MIN_ACTIVE_FETCH_SUCCESS:
        raise RuntimeError(f"quality gate: active Yahoo fetch success {active_success_rate:.1%} < {MIN_ACTIVE_FETCH_SUCCESS:.0%}")
    if active and active_action_rate < MIN_ACTIVE_FETCH_SUCCESS:
        raise RuntimeError(f"quality gate: active corporate-action fetch success {active_action_rate:.1%} < {MIN_ACTIVE_FETCH_SUCCESS:.0%}")
    return metrics


def select_cross_check_tickers(prices, tickers, limit=CROSS_CHECK_LIMIT):
    ranked = []
    for ticker in tickers:
        raw = prices.get(ticker)
        if raw and raw.get("c") and raw.get("v"):
            ranked.append((float(raw["c"][-1]) * float(raw["v"][-1]), ticker))
    return [ticker for _, ticker in sorted(ranked, reverse=True)[:limit]]


def split_adjust(dates, closes, split_events):
    """split_events: list of (date_int, ratio) -> คืนราคาที่ปรับ split แล้ว"""
    if not split_events:
        return closes
    out = []
    for d, c in zip(dates, closes):
        factor = 1.0
        for sd, ratio in split_events:
            if sd > d:
                factor *= ratio
        out.append(c / factor)
    return out


def accum_window(idx, closes, volumes):
    """หาหน้าต่างเวลา (วัน) ที่ใหญ่ที่สุดก่อนถึง index idx ที่ราคานิ่ง+volume เพิ่มขึ้น
    คืน 0 ถ้าไม่เจอแม้แต่หน้าต่างเล็กสุด"""
    best = 0
    for W in ACCUM_WINDOW_SIZES:
        if idx - W < 0:
            break
        seg_p = closes[idx - W:idx]
        seg_v = volumes[idx - W:idx]
        lo, hi = min(seg_p), max(seg_p)
        if lo <= 0:
            continue
        price_range_pct = (hi - lo) / lo
        half = W // 2
        v1 = sum(seg_v[:half]) / half if half else 0
        v2 = sum(seg_v[half:]) / (W - half) if (W - half) else 0
        if price_range_pct <= QUIET_PRICE_RANGE_PCT and v1 > 0 and v2 / v1 >= VOL_RISE_RATIO:
            best = W
    return best


def zigzag(points, pct=0.20):
    if len(points) < 2:
        return []
    pivots = []
    trend = None
    extreme_idx = 0
    extreme_price = points[0][1]
    for i in range(1, len(points)):
        _, p = points[i]
        if trend is None:
            change = (p - extreme_price) / extreme_price
            if change >= pct:
                trend = "up"; extreme_price = p; extreme_idx = i
            elif change <= -pct:
                trend = "down"; extreme_price = p; extreme_idx = i
        elif trend == "up":
            if p >= extreme_price:
                extreme_price = p; extreme_idx = i
            elif (p - extreme_price) / extreme_price <= -pct:
                pivots.append((extreme_idx, "peak")); trend = "down"; extreme_price = p; extreme_idx = i
        elif trend == "down":
            if p <= extreme_price:
                extreme_price = p; extreme_idx = i
            elif (p - extreme_price) / extreme_price >= pct:
                pivots.append((extreme_idx, "trough")); trend = "up"; extreme_price = p; extreme_idx = i
    final_type = "peak" if trend == "up" else ("trough" if trend == "down" else None)
    if final_type and (not pivots or pivots[-1][0] != extreme_idx):
        pivots.append((extreme_idx, final_type))
    start_type = "trough" if (pivots and pivots[0][1] == "peak") else "peak"
    result = [(0, start_type)] + pivots
    cleaned = []
    for idx, typ in result:
        if cleaned and cleaned[-1][0] == idx:
            continue
        cleaned.append((idx, typ))
    return cleaned


def ymd_to_iso(d):
    d = str(d)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def build_derived(prices, splits_raw, tickers):
    """คืน (yearend, cycles_compact, downlist) — splits_raw: {ticker: [{date, ratio}]} exact date"""
    yearend = {}
    cycles_compact = {}
    downlist = []

    max_overall_date = None

    for t in tickers:
        if t not in prices:
            continue
        dates = prices[t]["d"]
        closes = prices[t]["c"]
        if len(dates) < 5:
            continue

        split_events = [(int(e["date"].replace("-", "")), e["ratio"]) for e in splits_raw.get(t, [])]
        adj_closes = split_adjust(dates, closes, split_events)
        pts = list(zip(dates, adj_closes))
        vols = prices[t].get("v") or [0] * len(dates)

        # --- year-end close (ราคาปิดวันซื้อขายสุดท้ายของแต่ละปี, ปรับ split แล้ว) ---
        by_year_last = {}
        for d, c in pts:
            y = int(str(d)[:4])
            by_year_last[y] = c  # เดินตามลำดับวันที่ (dates เรียงแล้ว) -> ค่าสุดท้ายของปีคือค่าล่าสุด
        if len(by_year_last) >= 3:
            yearend[t] = {str(y): round(c, 4) for y, c in by_year_last.items()}

        latest_d, latest_p = dates[-1], adj_closes[-1]
        if max_overall_date is None or latest_d > max_overall_date:
            max_overall_date = latest_d

        # --- cycle (zigzag) ---
        if len(pts) < 30:
            continue
        pivots = zigzag(pts, pct=ZIGZAG_PCT)
        if len(pivots) < 2:
            continue
        events = [[ymd_to_iso(pts[idx][0]), round(pts[idx][1], 3), 1 if typ == "peak" else 0,
                   accum_window(idx, adj_closes, vols)]
                  for idx, typ in pivots]
        has_split = t in splits_raw
        # l = latest actual bar; the final ZigZag extreme can be earlier than today.
        cycles_compact[t] = {"sa": 1 if has_split else 0, "e": events,
                             "l": [ymd_to_iso(latest_d), round(latest_p, 3)]}

        # --- downlist: ราคาสูงสุดตั้งแต่จุดยืนยันล่าสุด เทียบราคาล่าสุด ---
        last_pivot_date_int = int(events[-1][0].replace("-", ""))
        tail = [(d, c) for d, c in pts if d >= last_pivot_date_int]
        if not tail:
            tail = [pts[-1]]
        peak_d, peak_p = max(tail, key=lambda x: x[1])
        pct_now = (latest_p - peak_p) / peak_p * 100
        days_now = (datetime.strptime(ymd_to_iso(latest_d), "%Y-%m-%d") - datetime.strptime(ymd_to_iso(peak_d), "%Y-%m-%d")).days
        downlist.append({
            "t": t, "pd": ymd_to_iso(peak_d), "pp": round(peak_p, 3),
            "cd": ymd_to_iso(latest_d), "cp": round(latest_p, 3),
            "pct": round(pct_now, 2), "days": days_now
        })

    # กรองเฉพาะหุ้นที่ยังเทรดจริง + กำลังต่ำกว่าจุดสูงสุดล่าสุด
    if max_overall_date:
        maxd = datetime.strptime(ymd_to_iso(max_overall_date), "%Y-%m-%d")
        downlist = [d for d in downlist
                    if (maxd - datetime.strptime(d["cd"], "%Y-%m-%d")).days <= ACTIVE_WINDOW_DAYS
                    and d["pct"] < 0]
    downlist.sort(key=lambda x: x["pct"])

    return yearend, cycles_compact, downlist


# -----------------------------------------------------------------------
# main
# -----------------------------------------------------------------------
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    tickers = load_tickers()
    print(f"tickers: {len(tickers)}")

    print("\n== STEP 1: update daily prices from Yahoo Finance ==")
    prices = load_prices()
    prices, price_report = update_prices(prices, tickers)

    print("\n== STEP 2: refresh splits & dividends ==")
    existing_splits = read_json_file("splits.json", {})
    existing_dividends = read_json_file("dividends.json", {})
    splits_raw, div_raw, action_report = fetch_splits_dividends(tickers)
    splits_sorted = merge_actions(existing_splits, sort_splits(splits_raw), "ratio")
    dividends_sorted = merge_actions(existing_dividends, sort_dividends(div_raw), "amount")
    quality = validate_store(prices, tickers, price_report, action_report)

    print("\n== STEP 2B: independent source cross-check (optional) ==")
    validation = cross_check(prices, select_cross_check_tickers(prices, tickers))
    quality["crossCheck"] = validation
    quality["generatedAt"] = datetime.now().isoformat(timespec="seconds")
    quality["status"] = ("warning" if validation["mismatchCount"] or validation["errorCount"] else
                         "ok" if validation["comparisonCount"] else "unverified")

    # Persist only after the quality gate passes; all writes are atomic.
    save_prices(prices)
    write_json_atomic("splits.json", splits_sorted)
    write_json_atomic("dividends.json", dividends_sorted)
    write_json_atomic("data_quality.json", quality, pretty=True)
    print(f"splits: {len(splits_sorted)} tickers, dividends: {len(dividends_sorted)} tickers")

    print("\n== STEP 3: recompute year-end / cycles / scanner signals ==")
    yearend, cycles_compact, downlist = build_derived(prices, splits_sorted, tickers)
    accumulation_signals = build_signals(prices, splits_sorted, tickers, ACTIVE_WINDOW_DAYS)
    write_json_atomic("stock_yearend.json", {"years": sorted({int(y) for v in yearend.values() for y in v}), "tickers": yearend})
    write_json_atomic("cycles_compact.json", cycles_compact)
    write_json_atomic("downlist.json", downlist)
    write_json_atomic("accumulation_signals.json", accumulation_signals)
    print(f"yearend: {len(yearend)} | cycles: {len(cycles_compact)} | signals: {len(accumulation_signals)}")

    print("\n== STEP 4: rebuild stock_toolkit.html ==")
    import build_toolkit_html  # ไฟล์ข้างๆ กัน — ประกอบ HTML จากไฟล์ data/*.json
    build_toolkit_html.build(DATA_DIR, OUTPUT_HTML)
    print(f"wrote {OUTPUT_HTML}")

    print("\n== DONE ==")
    print(f"last updated: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
