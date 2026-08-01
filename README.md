# SET Stock Toolkit — เครื่องคำนวณผลตอบแทน / วิเคราะห์ Cycle / สแกนหุ้นขาลง

เว็บเครื่องมือวิเคราะห์หุ้น SET (ไทย) 3 ฟีเจอร์ในหน้าเดียว อัปเดตข้อมูลอัตโนมัติทุกวันหลังตลาดปิด ผ่าน GitHub Actions
แล้ว host ฟรีด้วย GitHub Pages

## โครงสร้างโปรเจกต์

```
.
├── index.html                     ← เว็บที่ GitHub Pages จะ serve (ถูกสร้างใหม่ทุกวันโดยสคริปต์)
├── data/
│   ├── prices.json.gz             ← ราคารายวันดิบ (source of truth สะสมเรื่อยๆ, ไม่ commit ทับ ต่อยอดทุกวัน)
│   ├── splits.json                ← ข้อมูล stock split (รีเฟรชใหม่ทุกวัน)
│   ├── dividends.json             ← ข้อมูลปันผล (รีเฟรชใหม่ทุกวัน)
│   ├── stock_yearend.json         ← ราคาปิดสิ้นปี (คำนวณใหม่ทุกวัน)
│   ├── cycles_compact.json        ← จุด peak/trough ของทุกหุ้น (คำนวณใหม่ทุกวัน)
│   ├── downlist.json              ← รายชื่อหุ้นขาลงตอนนี้ (คำนวณใหม่ทุกวัน)
│   └── clean_tickers.txt          ← รายชื่อหุ้นที่ระบบติดตาม (965 ตัว, แก้เพิ่ม/ลดเองได้)
├── scripts/
│   ├── update_and_build.py        ← สคริปต์หลัก: ดึงข้อมูล + คำนวณ + build index.html
│   ├── build_toolkit_html.py      ← ประกอบ HTML จาก data/*.json (เรียกจากสคริปต์หลัก)
│   └── templates/                 ← ชิ้นส่วน HTML/CSS/JS ของแต่ละหน้า (ไม่ค่อยต้องแก้)
└── .github/workflows/
    └── daily-update.yml           ← ตั้ง cron รันทุกวัน 18:00 ICT (จ.-ศ.)
```

## วิธี Setup ครั้งแรก

1. **สร้าง repo ใหม่บน GitHub** (public หรือ private ก็ได้ — ถ้า private ต้องมี GitHub Pro ถึงจะเปิด Pages ได้ฟรี แนะนำ public)

2. **push โฟลเดอร์นี้ทั้งหมดขึ้น repo**
   ```bash
   cd stock-toolkit          # โฟลเดอร์ที่แตกไฟล์ zip นี้ออกมา
   git init
   git add .
   git commit -m "initial: bootstrap data + pipeline"
   git branch -M main
   git remote add origin https://github.com/<username>/<repo-name>.git
   git push -u origin main
   ```

3. **เปิด GitHub Pages**
   - เข้า repo → Settings → Pages
   - Source: "Deploy from a branch"
   - Branch: `main` / folder: `/ (root)`
   - กด Save — รอ 1-2 นาที จะได้ลิงก์ `https://<username>.github.io/<repo-name>/`

4. **เช็คว่า Actions มีสิทธิ์ push กลับได้**
   - เข้า repo → Settings → Actions → General → เลื่อนลงหา "Workflow permissions"
   - เลือก **"Read and write permissions"** แล้ว Save
   - (ถ้าไม่เปิดตรงนี้ Actions จะรันได้แต่ push กลับไม่ได้ ข้อมูลจะไม่อัปเดต)

5. **ทดสอบรันด้วยมือครั้งแรก**
   - เข้า repo → แท็บ Actions → เลือก workflow "Daily SET data update"
   - กด "Run workflow" (ปุ่มขวาบน) → รอสัก 15-25 นาที (ดึง ~965 หุ้นจาก Yahoo)
   - เสร็จแล้วเช็คว่ามี commit ใหม่ "auto: daily data update ..." เข้ามา

จากนั้นระบบจะรันเองทุกวันจันทร์-ศุกร์ 18:00 ICT โดยอัตโนมัติ ไม่ต้องทำอะไรเพิ่ม

## แก้เวลารันหรือรายชื่อหุ้น

- เวลา cron: แก้ `cron: "0 11 * * 1-5"` ใน `.github/workflows/daily-update.yml`
  (เวลาเป็น UTC เสมอ, ICT = UTC+7 — เช่นอยากรัน 19:00 ICT ก็คือ `0 12 * * 1-5`)
- รายชื่อหุ้น: แก้ไฟล์ `data/clean_tickers.txt` (บรรทัดละ 1 ticker ไม่ต้องมี `.BK`)
  หุ้นใหม่ที่เพิ่มเข้าไปจะเริ่มเก็บข้อมูลราคาตั้งแต่วันที่รันครั้งแรกหลังเพิ่ม (ย้อนหลังจะไม่มีถ้าไม่เคยมีในไฟล์ `prices.json.gz` มาก่อน)
- นิยาม cycle (20%) และ threshold "ยังเทรดอยู่" (60 วัน): แก้ค่าคงที่ด้านบนของ `scripts/update_and_build.py`
  (`ZIGZAG_PCT`, `ACTIVE_WINDOW_DAYS`)

## รันเองที่เครื่อง (ทดสอบก่อน push)

```bash
pip install yfinance --upgrade
python scripts/update_and_build.py
```
จะเขียนทับ `data/*.json`, `data/prices.json.gz`, และ `index.html` — เปิด `index.html` ด้วยเบราว์เซอร์ดูผลได้เลยก่อน commit

## ข้อจำกัดที่ควรรู้

- ข้อมูลราคา/split/ปันผลทั้งหมดมาจาก **Yahoo Finance (yfinance)** ผ่านตัว `.BK` suffix ของแต่ละ ticker — บางตัวข้อมูลอาจไม่ครบ/ล่าช้า/ผิดพลาดได้ โดยเฉพาะหุ้นเล็กที่สภาพคล่องต่ำ
- ทุกอย่างเป็นการวิเคราะห์ **pattern ราคาที่ผ่านมาแล้ว** ไม่ใช่การพยากรณ์อนาคต ไม่ใช่คำแนะนำการลงทุน
- ถ้า Yahoo เปลี่ยน API หรือบล็อก request จำนวนมาก สคริปต์อาจ error บางส่วน — เช็ค log ในแท็บ Actions ได้เสมอ
- `prices.json.gz` (~23MB, มี volume ด้วยแล้ว) จะถูก commit ทับทุกวันที่มีข้อมูลใหม่ ทำให้**ขนาด repo โตขึ้นเรื่อยๆ ตามจำนวนวัน** (ปีละหลาย GB ถ้านับรวมประวัติ commit) ถ้าเริ่มใหญ่เกินไป แก้ได้ด้วยการ squash ประวัติ commit เป็นระยะ (`git checkout --orphan`) หรือย้ายไปใช้ Git LFS
- คอลัมน์ "วันสะสม/ทยอยขายก่อนหน้า" ในหน้า Cycle Analyzer เป็น heuristic ง่ายๆ (ราคานิ่ง + volume ขึ้น) ปรับค่าคงที่ได้ที่ด้านบนของ `scripts/update_and_build.py` (`ACCUM_WINDOW_SIZES`, `QUIET_PRICE_RANGE_PCT`, `VOL_RISE_RATIO`) — ยังไม่ผ่านการพิสูจน์ทางสถิติ ใช้เป็นไอเดียเบื้องต้นเท่านั้น
