# PRD

DCA Planner

Phase 0

UX Foundation

Priority

Critical

Objective

ลด Cognitive Load

ให้ผู้ใช้เห็นคำตอบภายใน 5 วินาที

---

## Task 1

Executive Summary Card

เพิ่ม Card ด้านบนผลลัพธ์

ประกอบด้วย

- DCA Score
- Recommendation
- Risk
- Current Cycle
- Historical Confidence

ต้องอยู่เหนือทุก Section

---

## Task 2

Recommendation Card

แสดง

Strong Buy

Buy

Accumulate

Wait

Avoid

พร้อม

Recommended Allocation

เช่น

ลงทุนตอนนี้

30%

ถือเงินสด

70%

---

## Task 3

Reason Engine

แสดงเหตุผล

3-5 ข้อ

ตัวอย่าง

✓ อยู่ต่ำกว่า Median

✓ Downside จำกัด

✓ Historical Recovery สูง

✓ Cycle อยู่ในช่วงสะสม

---

## Task 4

Risk Meter

เปลี่ยนตัวเลข

เป็น

Visualization

LOW

██████░░░

MEDIUM

████████░

HIGH

██████████

---

## Task 5

Confidence

เพิ่ม

Historical Confidence

เช่น

82%

Based on historical similarity.

---

## UI Rules

ใช้ Card

ใช้ White Space มากขึ้น

Summary ต้องเห็นโดยไม่ Scroll

ใช้สี

Green

Yellow

Red

---

## Technical

สร้าง Component

components/dca/

SummaryCard

RecommendationCard

RiskMeter

ConfidenceBadge

ReasonList

---

## Refactor

ห้ามแก้ Business Logic

ใช้ข้อมูลเดิมทั้งหมด

เปลี่ยนเฉพาะ Presentation Layer

---

## Acceptance

เห็น Recommendation ภายใน 5 วินาที

ไม่ต้องอ่านตารางก็เข้าใจผล

Summary อยู่ด้านบนสุด