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
    dca_v2_style = _read("dca_v2_style.css")
    dca_wrap = _read("dca_wrap.html")
    dca_domain = _read("dca_domain.js")
    dca_script = _read("dca_script.js")

    swing_backtest = _read_json(data_dir, "swing_backtest.json", {})

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Cycle and DCA are loaded lazily from Appwrite with public data files as fallback.
    # Keep only an empty bootstrap object in index.html so the landing page stays small.
    cyc_script = cyc_script.replace("__CYCLES_JSON__", "{}")
    scan_script = (scan_script
                   .replace("__ACCUMULATION_JSON__", "[]")
                   .replace("__UPDATED_AT_JSON__", json.dumps(updated_at, ensure_ascii=False))
                   .replace("__SCAN_DIVIDENDS_JSON__", "{}"))
    swing_script = (swing_script
                    .replace("__SWING_JSON__", "[]")
                    .replace("__SWING_BACKTEST_JSON__", json.dumps(swing_backtest, ensure_ascii=False, separators=(",", ":"))))
    dca_script = dca_script.replace("__DCA_JSON__", "{}")

    html = f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>เครื่องมือวิเคราะห์หุ้น SET</title>
<style>
{nav_css}
{cyc_style}
{scan_style}
{swing_style}
{dca_style}
{dca_v2_style}
</style>
</head>
<body>
<div class="wrap">
  <div class="nav-tabs">
    <button class="nav-tab" id="navCycle">🌊 วิเคราะห์ Cycle</button>
    <button class="nav-tab active" id="navScan">🔎 คัดกรองหุ้น</button>
    <button class="nav-tab" id="navSwing">📈 Swing Trade</button>
    <button class="nav-tab" id="navDca">🗓️ DCA</button>
    <div class="nav-status-cluster">
      <span class="feature-source-status fallback" id="cycleSourceStatus" hidden>Cycle: รอโหลดข้อมูล</span>
      <span class="feature-source-status fallback" id="scanSourceStatus" hidden>คัดกรอง: รอโหลดข้อมูล</span>
      <span class="feature-source-status fallback" id="swingSourceStatus" hidden>Swing: รอโหลดข้อมูล</span>
      <span class="feature-source-status fallback" id="dcaSourceStatus" hidden>DCA: รอโหลดข้อมูล</span>
      <span class="cloud-data-status" id="cloudDataStatus" role="status" aria-live="polite">Cloud: checking...</span>
    </div>
  </div>

  <div class="page" id="pageCycle">
{cyc_wrap}
  </div>

  <div class="page active" id="pageScan">
{scan_wrap}
  </div>

  <div class="page" id="pageSwing">
{swing_wrap}
  </div>

  <div class="page" id="pageDca">
{dca_wrap}
  </div>

  <div class="stock-menu-backdrop" id="stockMenuBackdrop"></div>
  <aside class="stock-side-menu" id="stockSideMenu" aria-hidden="true">
    <div class="stock-menu-head"><b id="stockMenuTitle">เลือกหุ้น</b><button type="button" id="stockMenuClose" aria-label="ปิดรายชื่อหุ้น">×</button></div>
    <input id="stockMenuSearch" placeholder="ค้นหา Ticker..." autocomplete="off">
    <div class="stock-menu-groups" id="stockMenuGroups"></div>
    <div class="stock-menu-note">จัดกลุ่มตามตัวอักษร เนื่องจากระบบยังไม่มีข้อมูล Sector ที่ตรวจสอบแล้ว</div>
  </aside>
</div>

<script>
const MARKET_API_BASE = 'https://6a6f0c5a00324368985a.sgp.appwrite.run';
const MARKET_API_TIMEOUT_MS = 12000;
const MARKET_CACHE_NAME = 'th-stock-market-v1';
const MARKET_CACHE_TTL_MS = 6 * 60 * 60 * 1000;

function formatMarketDate(value) {{
  const text = String(value || '');
  return /^\\d{{8}}$/.test(text) ? `${{text.slice(6,8)}}/${{text.slice(4,6)}}/${{text.slice(0,4)}}` : text;
}}

function marketDataAgeDays(value) {{
  const text = String(value || '');
  if (!/^\\d{{8}}$/.test(text)) return null;
  const date = Date.UTC(Number(text.slice(0,4)), Number(text.slice(4,6)) - 1, Number(text.slice(6,8)));
  return Math.max(0, Math.floor((Date.now() - date) / 86400000));
}}

function setCloudSummaryStatus(element, label, payload, count) {{
  const age = marketDataAgeDays(payload?.dataAsOf);
  const source = payload?._clientSource === 'cache' ? 'Cache' : 'Cloud';
  const stale = age !== null && age > 4;
  element.className = `feature-source-status ${{stale ? 'stale' : 'online'}}`;
  element.textContent = `${{label}} ${{source}} ${{formatMarketDate(payload?.dataAsOf)}} · ${{Number(count).toLocaleString('en-US')}} หุ้น${{stale ? ` · เก่า ${{age}} วัน` : ''}}`;
  element.title = stale ? `ข้อมูลตลาดเก่ากว่าวันปัจจุบัน ${{age}} วัน โปรดตรวจสอบก่อนใช้วางแผน` : `${{source}} data · schema ${{payload?.schemaVersion ?? '-'}}`;
}}

function mergeTickerOptions(listId, tickers) {{
  const list = document.getElementById(listId);
  if (!list) return;
  const existing = new Set(Array.from(list.options).map(option => option.value));
  tickers.forEach(ticker => {{
    if (existing.has(ticker)) return;
    const option = document.createElement('option');
    option.value = ticker;
    list.appendChild(option);
  }});
}}

async function fetchMarketSummary(name, signal) {{
  const manifest = await window.marketManifestReady;
  if (manifest && !manifest.summaries?.includes(name)) throw new Error(`${{name}} summary unavailable`);
  const version = manifest ? `${{manifest.dataAsOf}}-${{manifest.schemaVersion}}` : 'latest';
  const cacheKey = new Request(`${{location.origin}}${{location.pathname}}?market-summary=${{encodeURIComponent(name)}}&version=${{encodeURIComponent(version)}}`);
  let cache = null;
  try {{
    if ('caches' in window) {{
      cache = await caches.open(MARKET_CACHE_NAME);
      const cached = await cache.match(cacheKey);
      if (cached) {{
        const savedAt = Number(cached.headers.get('x-th-stock-cached-at') || 0);
        if (Date.now() - savedAt < MARKET_CACHE_TTL_MS) {{
          const payload = await cached.json();
          payload._clientSource = 'cache';
          const compatible = name !== 'accumulation' || payload.summary?.some(item => Number.isFinite(Number(item.volume5Ratio)));
          if (compatible) return payload;
          await cache.delete(cacheKey);
        }}
        await cache.delete(cacheKey);
      }}
    }}
  }} catch (_) {{ cache = null; }}
  const response = await fetch(`${{MARKET_API_BASE}}/v1/summaries/${{name}}`, {{
    headers: {{Accept: 'application/json'}}, cache: 'no-store', signal,
  }});
  if (!response.ok) throw new Error(`${{name}} HTTP ${{response.status}}`);
  const payload = await response.json();
  if (name === 'accumulation' && !payload.summary?.some(item => Number.isFinite(Number(item.volume5Ratio)))) {{
    throw new Error('Cloud screener schema is older than this page');
  }}
  if (cache) {{
    try {{
      const keys = await cache.keys();
      await Promise.all(keys.filter(key => key.url.includes(`market-summary=${{encodeURIComponent(name)}}`)).map(key => cache.delete(key)));
      await cache.put(cacheKey, new Response(JSON.stringify(payload), {{
        headers: {{'content-type': 'application/json', 'x-th-stock-cached-at': String(Date.now())}},
      }}));
    }} catch (_) {{ /* Cache quota or privacy mode: network data remains usable. */ }}
  }}
  payload._clientSource = 'cloud';
  return payload;
}}

window.marketManifestReady = (async () => {{
  const status = document.getElementById('cloudDataStatus');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), MARKET_API_TIMEOUT_MS);
  try {{
    const response = await fetch(`${{MARKET_API_BASE}}/v1/manifest`, {{
      headers: {{Accept: 'application/json'}},
      cache: 'no-store',
      signal: controller.signal,
    }});
    if (!response.ok) throw new Error(`market API HTTP ${{response.status}}`);
    const manifest = await response.json();
    if (!Array.isArray(manifest.tickers) || !manifest.tickers.length) throw new Error('invalid market manifest');
    ['tickerList', 'cycTickerList', 'dcaTickerList'].forEach(id => mergeTickerOptions(id, manifest.tickers));
    const age = marketDataAgeDays(manifest.dataAsOf);
    const stale = age !== null && age > 4;
    status.textContent = `Cloud ${{formatMarketDate(manifest.dataAsOf)}} · ${{manifest.tickerCount.toLocaleString('en-US')}} หุ้น${{stale ? ` · เก่า ${{age}} วัน` : ''}}`;
    status.classList.add(stale ? 'stale' : 'online');
    status.title = stale ? `ข้อมูลตลาดเก่ากว่าวันปัจจุบัน ${{age}} วัน โปรดตรวจสอบก่อนใช้วางแผน` : `Appwrite staging · schema ${{manifest.schemaVersion}}`;
    return manifest;
  }} catch (error) {{
    status.textContent = 'ใช้ข้อมูลสำรองในหน้า';
    status.classList.add('fallback');
    status.title = `Market API unavailable: ${{error.message}}`;
    return null;
  }} finally {{
    clearTimeout(timer);
  }}
}})();

const navButtons = {{navCycle:'pageCycle', navScan:'pageScan', navSwing:'pageSwing', navDca:'pageDca'}};
const navFeatureStatuses = {{navCycle:'cycleSourceStatus', navScan:'scanSourceStatus', navSwing:'swingSourceStatus', navDca:'dcaSourceStatus'}};
Object.keys(navButtons).forEach(navId => {{
  document.getElementById(navId).addEventListener('click', () => {{
    Object.entries(navButtons).forEach(([nId, pId]) => {{
      document.getElementById(nId).classList.toggle('active', nId===navId);
      document.getElementById(pId).classList.toggle('active', pId===navButtons[navId]);
    }});
    Object.values(navFeatureStatuses).forEach(id => document.getElementById(id).hidden = id !== navFeatureStatuses[navId]);
  }});
}});

(function(){{
{cyc_script}
}})();

{scan_script}
{swing_script}
{dca_domain}
{dca_script}
document.getElementById('navScan').click();
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
