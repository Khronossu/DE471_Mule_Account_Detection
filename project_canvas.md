Project Canvas

Problem Statement:
ปัญหา:
การหลอกลวงทางการเงิน (Scam) และการใช้บัญชีม้า (Mule Accounts) ในระบบธนาคารไทย สร้างความเสียหายให้แก่ประชาชนและสถาบันการเงินเป็นจำนวนมากในแต่ละปี
บัญชีม้าถูกใช้เป็น "ทางผ่าน" ในการฟอกเงิน โดยรับเงินจากเหยื่อแล้วกระจายโอนออกไปหลายทอด (Multi-hop Laundering) ก่อนส่งออกไปยังปลายทาง เช่น Crypto Wallet หรือบัญชีต่างประเทศ ทำให้ยากต่อการติดตามและตรวจจับ

เป้าหมายของโปรเจกต์นี้คือ:
วิเคราะห์ "รูปแบบพฤติกรรม" ของธุรกรรมที่ผิดปกติ ผ่าน Behavioral Features ที่สร้างจาก Synthetic Data
และสรุป Insight เชิงบรรยาย/วินิจฉัย (Descriptive & Diagnostic) เพื่อช่วยธนาคารคัดกรองความเสี่ยงได้อย่างมีประสิทธิภาพ
(ขอบเขตโปรเจกต์: Data Engineering + EDA เท่านั้น — ไม่รวมเฟส Machine Learning)

---

SMART Objectives
S — Specific:
   วิเคราะห์พฤติกรรมบัญชีม้า (Burner/Sleeper) ผ่านรูปแบบการทำธุรกรรม — ยอดเงิน, ความถี่, อายุบัญชี, พฤติกรรม Pass-through — เพื่อระบุ "สัญญาณเชิงปริมาณ" ที่แยกบัญชีม้าออกจากบัญชีปกติได้

M — Measurable (ต้องบรรลุทุก Target ต่อไปนี้):
   1. Dwell Time: ≥ 90% ของธุรกรรมม้า (Hop 2–3) มี Dwell Time < 5 นาที
      — เทียบกับบัญชีปกติที่คาดว่าจะมี < 5% ของธุรกรรมอยู่ในช่วงนี้
   2. In/Out Ratio 7 วัน: Mule Rate ในกลุ่มบัญชีที่มี Ratio อยู่ระหว่าง 0.9–1.0
      ต้องสูงกว่าค่าเฉลี่ยภาพรวมอย่างน้อย 2 เท่า (Lift ≥ 2.0x)
   3. Burst Score: ≥ 80% ของธุรกรรม Hop 2 มี Burst Score (จำนวนโอนต่อชั่วโมง) ≥ 3
   4. Account Age: Burner ทุกบัญชีต้องมี Account Age < 30 วัน ณ วันที่เกิดธุรกรรมม้า
   5. Hourly Pattern: สัดส่วนธุรกรรมม้าที่เกิดในช่วง 00:00–06:00 ต้องสูงกว่าค่าเฉลี่ยของบัญชีปกติอย่างน้อย 2 เท่า

A — Achievable:
   สร้างชุดข้อมูลจำลอง (Synthetic Data) ~20,000 ธุรกรรม จาก 1,000 บัญชี โดยจำลอง 20 Mule Rings
   แบบ Non-overlapping (ทุก Ring ใช้สมาชิกไม่ซ้ำกัน) ที่สะท้อนพฤติกรรมการโกงในโลกความเป็นจริง

R — Relevant:
   ผลลัพธ์ที่ได้สามารถใช้เป็น Rule-based Risk Indicators ให้ทีมธนาคารนำไปคัดกรองบัญชีต้องสงสัยได้ทันที
   โดยไม่ต้องรอ Machine Learning Model

T — Time-bound:
   ดำเนินการสร้าง Data Pipeline, Feature Engineering และสรุปผล EDA Insight ให้สำเร็จภายในระยะเวลา Final Submission

---

5W1H — Business Questions (คำถามที่ใช้ขับการวิเคราะห์)

WHO — บัญชีแบบใดมีแนวโน้มเป็นบัญชีม้ามากที่สุด?
   → วิเคราะห์ตาม risk_segment, kyc_status, employment_status, และ account_age
   → คาดการณ์: Burner มีอายุบัญชีน้อย, Sleeper เป็นบัญชีเก่าที่ถูก recruit

WHAT — ธุรกรรมแบบใดที่ถือว่า "ผิดปกติ"?
   → วัดผ่าน amount_z_score, ขนาดยอดโอน, และความสัมพันธ์ผู้รับ (First-Time Payee)
   → คำถามย่อย: ยอดผิดปกติ (Z-Score > 2) เกิดใน Mule Transactions คิดเป็นสัดส่วนเท่าใด?

WHERE — ช่องทางการโอนใดที่มีความเสี่ยงสูง?
   → เปรียบเทียบ Mule Rate ต่อ transfer_method (Mobile App / Web / API / ATM)
   → คำถามย่อย: ช่อง API ถูกใช้ใน Hop 2–3 ในสัดส่วนเท่าใดเมื่อเทียบกับธุรกรรมปกติ?

WHEN — ธุรกรรมม้าเกิดช่วงเวลาใดของวัน?
   → วิเคราะห์ Hourly Distribution ของ is_mule_tx
   → คำถามย่อย: ช่วง 00:00–06:00 มีสัดส่วน Mule Transactions สูงกว่าช่วงอื่นจริงหรือไม่?

WHY — เหตุใดพฤติกรรม Pass-through จึงเป็นสัญญาณสำคัญ?
   → เชื่อมโยง in_out_ratio_7d + dwell_time_minutes เพื่ออธิบายวงจรฟอกเงิน

HOW — บัญชีม้าเคลื่อนย้ายเงินอย่างไร?
   → วิเคราะห์ Topology ของ Mule Ring: Victim → Sleeper → Burner(s) → Crypto Wallet
   → คำถามย่อย: Burst Score (ความถี่โอนต่อชั่วโมง) ใน Hop 2 สูงกว่าธุรกรรมปกติกี่เท่า?

---

Data Dictionary (สรุป — ดูรายละเอียดเต็มใน DataDict.md)

Star Schema: 2 Dimension + 1 Fact แปลงเป็น One Big Table (OBT) สำหรับ BI

dim_customers (5 fields): customer_id (PK), age, employment_status, kyc_status, risk_segment
dim_accounts  (6 fields): account_id (PK), customer_id (FK), account_creation_date, initial_deposit, is_mule_flag, mule_type
fact_transactions (17 fields):
   Raw: transaction_id (PK), sender_account_id (FK), receiver_account_id (FK), amount, transaction_timestamp, transfer_method, is_mule_tx
   Engineered Features:
   • dwell_time_minutes — เวลาตั้งแต่รับเงินจนโอนออก (Pass-through indicator)
   • in_out_ratio_7d — อัตราส่วนเงินเข้า/ออก 7 วัน (Pass-through strength)
   • is_first_time_payee — เคยโอนให้ผู้รับรายนี้มาก่อนหรือไม่
   • amount_z_score — ยอดผิดปกติเทียบประวัติผู้โอน
   • daily_tx_count_sender — จำนวนธุรกรรมใน 24 ชั่วโมง
   • burst_score — จำนวนธุรกรรมใน 1 ชั่วโมง (ตรวจจับ Burst Pattern)
   • account_age_days — อายุบัญชีผู้โอน ณ เวลาทำธุรกรรม (Burner indicator)
   • time_since_last_tx_seconds — ความเร็วในการโอนต่อเนื่อง
   • sender_balance_before_tx / receiver_balance_before_tx — ยอดคงเหลือก่อนธุรกรรม

Data Scale: 1,000 customers | 80 mule accounts (20 Sleepers + 60 Burners) | ~20,000 transactions
Mule Ring Design: 20 rings, Non-overlapping (แต่ละ ring ใช้สมาชิกเฉพาะตัว ไม่ซ้ำกับ ring อื่น)
Mule Rate: ~1% (Highly Imbalanced แต่สะท้อนความเป็นจริง)

---

Key Business Metrics (KPIs ที่ใช้ตอบคำถามธุรกิจ)

Note: "Engineered Features" ในตารางข้างต้นเป็นตัวแปรระดับแถว (row-level) ส่วน Business Metrics ด้านล่างเป็น
ตัวชี้วัดระดับสรุป (aggregate) ที่คำนวณจาก Features เหล่านั้นเพื่อตอบคำถามเชิงธุรกิจโดยตรง:

| KPI | สูตรคำนวณ | คำถามธุรกิจที่ตอบ | เกณฑ์เป้าหมาย |
| :--- | :--- | :--- | :--- |
| Mule Dwell Rate | % ของ mule_tx ที่มี dwell_time_minutes < 5 | WHY: Pass-through เป็นสัญญาณจริงหรือ? | ≥ 90% |
| In/Out Mule Lift | Mule Rate ในกลุ่ม Ratio 0.9–1.0 ÷ Mule Rate ภาพรวม | WHY: Pass-through แยกม้าได้จริงหรือ? | ≥ 2.0x |
| Night Activity Lift | % mule_tx ในช่วง 00:00–06:00 ÷ % normal_tx ช่วงเดียวกัน | WHEN: เวลากลางคืนเสี่ยงจริงหรือ? | ≥ 2.0x |
| API Channel Concentration | % mule_tx ที่ใช้ transfer_method = API | WHERE: ช่อง API ถูกใช้ในฟอกเงินจริงหรือ? | ≥ 50% |
| Burst Incidence | % mule_tx ที่มี burst_score ≥ 3 | HOW: Mule Ring โอนถี่ผิดปกติจริงหรือ? | ≥ 80% (Hop 2) |
| Burner Age Compliance | % Burner ที่มี account_age_days < 30 | WHO: Burner เป็นบัญชีเปิดใหม่จริงหรือ? | 100% |

---

Technique Note: Amount Z-Score

**Z-Score** คือค่าสถิติที่บอก "ยอดโอนแต่ละรายการเบี่ยงเบนจากพฤติกรรมเดิมของผู้โอนมากแค่ไหน"

สูตร:  `Z = (amount − mean_historical) / std_historical`

การตีความ:
- |Z| < 1  → ปกติ (อยู่ในพฤติกรรมเดิม)
- |Z| ระหว่าง 1–2 → ค่อนข้างสูง
- |Z| > 2  → ผิดปกติอย่างมีนัยสำคัญ (outlier)

เหตุผลที่ใช้ **Expanding Mean/Std** (ไม่ใช่ค่าเฉลี่ยรวม): เพื่อคำนวณ Z-Score โดยใช้เฉพาะธุรกรรมในอดีตของผู้โอนเอง — ป้องกัน Data Leakage จากอนาคต และสะท้อนวิธีที่ระบบ Real-time Fraud Detection ทำงานจริง

---

EDA Insights (ผลการวิเคราะห์เบื้องต้น)
จากการวิเคราะห์ EDA บน Tableau Dashboard พบ 3 Insights หลัก:

Insight 1: Dwell Time (ยืนยันสมมติฐาน)
   บัญชีม้ามี Dwell Time ต่ำกว่าบัญชีปกติอย่างชัดเจน → ยืนยันพฤติกรรม "รับเงินแล้วโอนออกทันที" (Pass-through)
   เทคนิค: ใช้ Log Scale เพื่อจัดการ Imbalanced Data

Insight 2: In/Out Ratio (ยืนยันสมมติฐาน)
   บัญชีที่มี In/Out Ratio 0.9–1.0 มี Mule Rate สูงสุด — สูงกว่ากลุ่มอื่นอย่างมีนัยสำคัญ
   → ยืนยันว่าม้ารับเงินเข้าเท่าไหร่ก็โอนออกเท่านั้น

Insight 3: First-Time Payee (แก้ไขจากเฟสก่อน)
   หลังปรับ Data Generation ให้ Ring ไม่ใช้สมาชิกซ้ำ — สัญญาณ First-Time Payee กลับมาสะท้อนพฤติกรรมจริง
   (Burner ทุกบัญชีถูกโอนให้เป็นครั้งแรกในแต่ละ ring)

---

Limitations
ข้อจำกัดที่เหลืออยู่:
1. ข้อมูลเป็น Synthetic Data — พฤติกรรมบางอย่างยังเป็นการสมมติ ไม่สามารถทดแทนข้อมูลจริงได้ 100%
2. Class Imbalance (~1%) — ยังต้องใช้เทคนิค Log Scale / Percentile ในการ visualize
3. จำกัดที่ 20 Rings แบบ Non-overlapping — ยังไม่ครอบคลุมกรณี Mule Ring ซ้อนทับ (Overlapping Rings) ในโลกจริง

การปรับปรุงในเฟสนี้ (Final Submission):
• ✅ ปรับ Mule Ring ไม่ให้ใช้ sleeper/burner ซ้ำข้าม ring — แก้ปัญหา First-Time Payee signal
• ✅ เพิ่ม Time Bias — ธุรกรรมม้ากระจุกตัวในช่วง 00:00–06:00 ตามสมมติฐาน
• ✅ เพิ่ม Feature ใหม่: burst_score (ความถี่โอนต่อชั่วโมง) และ account_age_days (อายุบัญชี)
• ✅ ปรับ Amount Distribution ของธุรกรรมปกติให้เป็น Log-normal (สมจริงกว่า Uniform)
