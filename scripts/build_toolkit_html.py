"""
build_toolkit_html.py
======================
ประกอบ stock_toolkit.html จากไฟล์ data/*.json + template ใน scripts/templates/
เรียกใช้จาก update_and_build.py (ไม่ต้องรันตรงๆ)
"""

import json
import os
from datetime import datetime

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _read(name):
    with open(os.path.join(TEMPLATE_DIR, name), encoding="utf-8") as f:
        return f.read()


def _read_json(data_dir, name, default):
    path = os.path.join(data_dir, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build(data_dir, output_path):
    calc_style = _read("calc_style.css")
    calc_wrap = _read("calc_wrap.html")
    calc_script = _read("calc_script.js")
    cyc_style = _read("cyc_style.css")
    cyc_wrap = _read("cyc_wrap.html")
    cyc_script = _read("cyc_script.js")
    nav_css = _read("nav.css")
    scan_style = _read("scan_style.css")
    scan_wrap = _read("scan_wrap.html")
    scan_script = _read("scan_script.js")
    swing_style = _read("swing_style.css")
    swing_wrap = _read("swing_wrap.html")
    swing_script = _read("swing_script.js")
    dca_style = _read("dca_style.css")
    dca_wrap = _read("dca_wrap.html")
    dca_script = _read("dca_script.js")

    stock_yearend = _read_json(data_dir, "stock_yearend.json", {"years": [], "tickers": {}})
    splits = _read_json(data_dir, "splits.json", {})
    dividends = _read_json(data_dir, "dividends.json", {})
    cycles = _read_json(data_dir, "cycles_compact.json", {})
    downlist = _read_json(data_dir, "downlist.json", [])
    accumulation_signals = _read_json(data_dir, "accumulation_signals.json", [])
    swing_signals = _read_json(data_dir, "swing_signals.json", [])
    swing_backtest = _read_json(data_dir, "swing_backtest.json", {})
    dca_compact = _read_json(data_dir, "dca_compact.json", {})

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    calc_script = (calc_script
                   .replace("__DATA_JSON__", json.dumps(stock_yearend, ensure_ascii=False, separators=(",", ":")))
                   .replace("__SPLITS_JSON__", json.dumps(splits, ensure_ascii=False, separators=(",", ":")))
                   .replace("__DIVIDENDS_JSON__", json.dumps(dividends, ensure_ascii=False, separators=(",", ":"))))
    cyc_script = cyc_script.replace("__CYCLES_JSON__", json.dumps(cycles, ensure_ascii=False, separators=(",", ":")))
    scan_script = (scan_script
                   .replace("__DOWNLIST_JSON__", json.dumps(downlist, ensure_ascii=False, separators=(",", ":")))
                   .replace("__ACCUMULATION_JSON__", json.dumps(accumulation_signals, ensure_ascii=False, separators=(",", ":")))
                   .replace("__UPDATED_AT_JSON__", json.dumps(updated_at, ensure_ascii=False))
                   .replace("__SCAN_DIVIDENDS_JSON__", json.dumps(dividends, ensure_ascii=False, separators=(",", ":"))))
    swing_script = (swing_script
                    .replace("__SWING_JSON__", json.dumps(swing_signals, ensure_ascii=False, separators=(",", ":")))
                    .replace("__SWING_BACKTEST_JSON__", json.dumps(swing_backtest, ensure_ascii=False, separators=(",", ":"))))
    dca_script = dca_script.replace("__DCA_JSON__", json.dumps(dca_compact, ensure_ascii=False, separators=(",", ":")))

    html = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>เครื่องมือวิเคราะห์หุ้น SET</title>
<style>
{calc_style}
{nav_css}
{cyc_style}
{scan_style}
{swing_style}
{dca_style}
</style>
</head>
<body>
<div class="wrap">
  <div class="nav-tabs">
    <button class="nav-tab active" id="navCalc">📊 เครื่องคำนวณผลตอบแทน</button>
    <button class="nav-tab" id="navCycle">🌊 วิเคราะห์ Cycle</button>
    <button class="nav-tab" id="navScan">🎯 จังหวะสะสม</button>
    <button class="nav-tab" id="navSwing">📈 Swing Trade</button>
    <button class="nav-tab" id="navDca">🗓️ DCA</button>
  </div>

  <div class="page active" id="pageCalc">
{calc_wrap}
  </div>

  <div class="page" id="pageCycle">
{cyc_wrap}
  </div>

  <div class="page" id="pageScan">
{scan_wrap}
  </div>

  <div class="page" id="pageSwing">
{swing_wrap}
  </div>

  <div class="page" id="pageDca">
{dca_wrap}
  </div>
</div>

<script>
const navButtons = {{navCalc:'pageCalc', navCycle:'pageCycle', navScan:'pageScan', navSwing:'pageSwing', navDca:'pageDca'}};
Object.keys(navButtons).forEach(navId => {{
  document.getElementById(navId).addEventListener('click', () => {{
    Object.entries(navButtons).forEach(([nId, pId]) => {{
      document.getElementById(nId).classList.toggle('active', nId===navId);
      document.getElementById(pId).classList.toggle('active', pId===navButtons[navId]);
    }});
  }});
}});

(function(){{
{calc_script}
}})();

(function(){{
{cyc_script}
}})();

{scan_script}
{swing_script}
{dca_script}
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return len(html)


if __name__ == "__main__":
    # ทดสอบรันตรงๆ: python build_toolkit_html.py <data_dir> <output_path>
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "../data"
    o = sys.argv[2] if len(sys.argv) > 2 else "../stock_toolkit.html"
    n = build(d, o)
    print(f"wrote {o} ({n} bytes)")
