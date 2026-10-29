# Lab 2: Counting problems (Attribute control charts)

**Time:** about 60 minutes  **Tool:** QualityLab app  **Deliverable:** answers to the questions plus a short recommendation (half a page)

## Learning objectives

1. Choose correctly among p, np, c and u charts.
2. Explain why p- and u-chart limits change from point to point.
3. Recognize overdispersion in very large samples and use Laney's p′ chart.
4. Use a control chart to show that an improvement actually worked.

Use your **personal dataset code** in every part.

---

## Part A: Accounts-payable invoice errors (p chart)

Scenario: **Accounts-payable invoice errors**. Each week the AP team audits a different number of invoices and counts those with any error.

**A1.** Why is a **p** chart a better choice here than an **np** chart? Build the p chart (sample size column = `invoices_audited`).

**A2.** Why are the control limits not straight lines? In which kind of week are they widest?

**A3.** Which week signals? The audit log shows that week coincided with an ERP software update. Exclude that week and describe how the center line changes. What is the "normal" error rate of this process?

**A4.** The CFO asks for "zero invoice errors next quarter". Using the chart, explain what the process will deliver if nothing about it changes, and what would have to change to do better.

## Part B: E-commerce returns (p vs Laney p′)

Scenario: **E-commerce returns (very large samples)**. Each week 18,000–42,000 orders ship.

**B1.** First **uncheck** the Laney option to build a standard p chart. How many weeks are flagged? What does the app say about overdispersion?

**B2.** Now check **Laney adjustment**. How many weeks are flagged now? By what factor were the limits widened?

**B3.** In two or three sentences: why do huge samples make the standard p chart "cry wolf"? (Hint: the true return rate itself wobbles a little from week to week, for reasons no one would call a special cause, such as seasonality and product mix.)

## Part C: Circuit-board defects (c chart)

Scenario: **Circuit-board defects**. Every board is the same model.

**C1.** Why is a **c** chart appropriate, and why would a p chart be wrong here?

**C2.** Which board (by ID) signals? Use **Point labels → board_id**.

**C3.** Recompute the limits without that board. Is the remaining process in control?

## Part D: Did the training work? (u chart)

Scenario: **Hotel guest complaints**. Complaints are counted monthly. Guest-nights (the area of opportunity) vary by month. A front-desk training program ran at some point.

**D1.** Build a **u** chart (units column = `guest_nights_thousands`) with the first **12** months as Phase I. Which rule signals, and from which month?

**D2.** Explain how a chart can show a real improvement even when few or no points fall *below* the LCL.

**D3.** When did the improvement most likely start? (Count back from the first signal.)

**D4.** The improvement is real. What should the hotel do with the control limits now?

## Deliverable

Answer every numbered question briefly. Then write a half-page recommendation to the hotel's general manager (Part D): did the training work, how sure are you, and how should complaints be monitored from now on? Attach the u chart PNG.

### Rubric (20 points)

| Criterion | Points |
|---|---|
| Correct chart choice and justification (A1, C1) | 4 |
| Correct signals identified in each part | 6 |
| Overdispersion explained (B3) | 3 |
| Improvement detected and correctly dated (D1–D3) | 4 |
| Recommendation (D4 and memo) | 3 |
