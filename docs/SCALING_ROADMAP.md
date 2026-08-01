# Scaling and Data Architecture Roadmap

เอกสารนี้บันทึกแนวทางปรับโครงสร้างเมื่อจำนวนตลาด ข้อมูล หรือผู้ใช้งานเพิ่มขึ้น
ไม่จำเป็นต้องดำเนินการทั้งหมดในเวอร์ชันปัจจุบัน

## สถานะปัจจุบัน

- Static site บน GitHub Pages
- ข้อมูลที่ใช้แสดงผลถูกฝังใน `index.html`
- Browser ของผู้ใช้เป็นผู้คำนวณ Cycle, Swing และ DCA
- `prices.json.gz` เป็น source of truth และถูกอัปเดตรายวัน
- ไม่มีบัญชีผู้ใช้หรือข้อมูลที่ผู้ใช้บันทึกกลับ server

ข้อดีคือไม่มี database connection หรือ application server ที่เป็นคอขวด แต่หน้าเว็บจะโตตาม
จำนวน ticker และระยะเวลาข้อมูล ปัจจุบัน `index.html` มีขนาดประมาณ 6 MB

## Phase 1 — ลดขนาดหน้าเว็บ

เป้าหมาย: ผู้ใช้โหลดเฉพาะข้อมูลที่กำลังใช้งาน

1. แยก CSS และ JavaScript ออกจาก `index.html`
2. แยก derived data ตามฟังก์ชัน
   - `data/swing.json`
   - `data/accumulation.json`
   - `data/cycles/<ticker>.json`
   - `data/dca/<ticker>.json`
3. ใช้ `fetch()` โหลดข้อมูลเมื่อเปิดหน้าและเลือก ticker
4. ใส่ data version ในชื่อไฟล์หรือ query string เพื่อควบคุม cache
5. ตั้ง cache สำหรับไฟล์ที่ไม่เปลี่ยนระหว่างวัน
6. แสดง loading/error state เมื่อไฟล์โหลดไม่สำเร็จ

เกณฑ์เริ่ม Phase 1: `index.html` เกิน 8–10 MB หรือมีผู้ใช้รายงานว่าเปิดหน้าเว็บช้า

## Phase 2 — ย้าย raw history ออกจาก Git

เป้าหมาย: ลดขนาด repository และประวัติ commit

1. เก็บราคาดิบใน Object Storage เช่น S3-compatible storage
2. เก็บเป็น Parquet แบ่งตาม market/year หรือ market/ticker
3. Git เก็บเฉพาะโค้ด, schema และ derived data ขนาดเล็ก
4. Pipeline ดาวน์โหลดเฉพาะ partition ที่ต้องอัปเดต
5. มี checksum, backup และ retention policy

หลีกเลี่ยงการใช้ Git LFS เป็นแหล่งข้อมูลของ GitHub Pages เพราะ Pages ไม่รองรับการ serve
LFS objects โดยตรงเหมือนไฟล์ปกติ

## Phase 3 — Multi-market

สร้าง instrument metadata กลาง:

```json
{
  "symbol": "AAPL",
  "market": "US",
  "assetType": "equity",
  "currency": "USD",
  "timezone": "America/New_York",
  "providerSymbol": "AAPL",
  "benchmark": "SPY",
  "liquidityThreshold": 1000000
}
```

Data provider ต้องคืน schema กลาง:

```text
date, open, high, low, close, volume, dividend, split
```

ส่วนวิเคราะห์ห้ามผูกกับ suffix `.BK`, สกุลบาท หรือ timezone ของไทย

## Phase 4 — API and Database

เริ่มใช้ backend เมื่อมีบัญชีผู้ใช้, portfolio, watchlist, trade journal, alert, intraday
หรือ query ข้ามตลาดจำนวนมาก

โครงสร้างแนะนำ:

```text
Market data providers
        ↓
Ingestion and quality gate
        ↓
PostgreSQL / TimescaleDB + Object Storage
        ↓
API + cache
        ↓
Web application + CDN
```

- PostgreSQL: instruments, corporate actions, users, portfolios และแผน DCA
- TimescaleDB/Parquet: OHLCV time series
- Object Storage: raw files, backups และ derived snapshots
- Redis: cache, jobs และ alerts เมื่อจำเป็น

## Migration Safety

ก่อนย้ายทุก phase ต้องมี:

- Schema version
- Point-in-time tests
- Split/dividend reconciliation
- Row-count และ latest-date quality gates
- Backup และ rollback procedure
- เปรียบเทียบผล Cycle/Swing/DCA ก่อนและหลัง migration
- ห้ามเปลี่ยน data source และ scoring model พร้อมกันใน deployment เดียว

## Monitoring Metrics

- ขนาด `index.html` และ derived JSON
- เวลาโหลดหน้าแรกและเวลาเลือก ticker
- Git repository size
- จำนวน Yahoo fetch errors/empty responses
- จำนวน cross-source mismatches
- GitHub Pages bandwidth estimate
- จำนวน active tickers ที่ข้อมูลล่าช้าเกิน 1/7/60 วัน

