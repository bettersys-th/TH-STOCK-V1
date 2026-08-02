# DCA package roadmap

เอกสารนี้กำหนดขอบเขตเบื้องต้นเท่านั้น ยังไม่มีระบบสมาชิกหรือชำระเงินจริง และไม่ควรใช้การซ่อนปุ่มฝั่ง browser เป็นการตรวจสิทธิ์เมื่อเปิดขายแพ็กเกจ

## Free

- DCA Risk Planner และ Price-based Safety Monitor
- หลายหุ้นไม่เกิน 12 แท็บต่อ workspace
- Auto-save ใน browser
- บันทึกแผนหลักใน browser 1 ชุด
- งบแยกต่อหุ้น หรือแบ่งงบรวมเท่ากัน
- Historical Backtest และ Scenario พื้นฐาน

## Pro (future)

- หลาย named portfolios และจำนวนหุ้นที่สูงขึ้น
- กำหนดสัดส่วนงบรายหุ้นแบบ custom weights
- Conditional DCA / Buy Below / Buy Zones
- Export/Import, PDF/CSV report และ Cloud Sync
- แจ้งเตือนเมื่อราคาเข้าโซนหรือ Safety Monitor เปลี่ยนสถานะ
- Scenario และ portfolio comparison ขั้นสูง

## Technical boundary

- สูตรคำนวณหลักควรใช้ร่วมกันทุกแพ็กเกจ เพื่อไม่ให้ผลลัพธ์ Free และ Pro ขัดกัน
- สิทธิ์ Pro ต้องตรวจจาก backend/session ไม่ใช่ JavaScript flag อย่างเดียว
- ข้อมูลพอร์ตบน cloud ต้องแยกตาม user ID, เข้ารหัสระหว่างส่ง และมีการลบ/ส่งออกข้อมูลได้
- Local workspace ใช้ `localStorage` จึงผูกกับ browser/device และอาจหายเมื่อผู้ใช้ล้างข้อมูล
- ก่อนเปิดชำระเงินต้องเพิ่ม authentication, entitlement API, payment webhook, database migration และ audit log

## Suggested entitlement keys

- `portfolio.named.multiple`
- `portfolio.custom_weights`
- `portfolio.cloud_sync`
- `portfolio.export`
- `dca.conditional`
- `alerts.price_safety`

