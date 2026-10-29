# Lab 3: Can we meet the customer's spec, and where do we start? (Capability and Pareto)

**Time:** about 60 minutes  **Tool:** QualityLab app  **Deliverable:** a two-page improvement proposal

## Learning objectives

1. Check stability before computing capability, and explain why the order matters.
2. Compute and interpret Cp, Cpk, Pp and Ppk, including their confidence intervals.
3. Tell a *spread* problem from a *centering* problem, and price each fix.
4. Use a Pareto chart to choose where improvement effort pays off.

Use your **personal dataset code** throughout.

---

## Part A: Machined shafts

Scenario: **Machined shaft diameter**. Spec 25.00 ± 0.05 mm. A customer requires **Cpk ≥ 1.33**.

**A1.** On the **Control chart** tab, build an X̄-R chart from `part_1`–`part_4`. Is the process stable? Why must you check this *before* the Capability tab?

**A2.** On the **Capability** tab, record Cp, Cpk, Pp and Ppk with their 95% confidence intervals. Does the process meet the customer's requirement? Does the *lower* end of the Cpk interval meet it?

**A3.** Cp is noticeably larger than Cpk. What does that tell you? Calculate how far (in mm) the mean must move, and in which direction, to center the process. What would Cpk become if it were perfectly centered?

**A4.** Compare the expected PPM out of spec (within) before and after centering. If a shaft out of spec costs $40 to scrap and the plant makes 200,000 shafts a year, what is the annual saving from centering?

**A5.** Should the plant (a) buy a more precise lathe, (b) re-center the existing process, or (c) tighten inspection? Justify your answer with your numbers.

## Part B: Capability of an unstable process

Scenario: **Cold-brew bottle fill volume** (the line from Lab 1). Open the **Capability** tab.

**B1.** The app warns you about something. What is it?

**B2.** Compare Cpk with Ppk. Which number better describes what customers actually received during these 30 samples? Which better describes what the line *could* do if the special cause were removed?

**B3.** In one sentence: why is a capability index for an unstable process "a prediction of nothing"?

## Part C: Customer complaints (Pareto)

Scenario: **Customer complaint reasons**. Open the **Pareto** tab.

**C1.** Which categories make up the "vital few" (about 80% of complaints)?

**C2.** The customer-service director wants to start with "Rude support agent" because it is the most embarrassing. Using the chart, how do you respond?

**C3.** A Pareto chart ranks by **frequency**, not by **cost**. Suppose each complaint costs the company, on average: late delivery $8 (goodwill credit), wrong item shipped $35 (return shipping plus reshipment), damaged packaging $20 and billing error $15. Re-rank these four categories by total cost. Does your priority change? Why might a cost-weighted Pareto be the better tool for a manager?

## Deliverable: improvement proposal (two pages)

Choose **either** the shaft process (Part A) **or** the complaints (Part C) and write a proposal to the plant or operations manager that:

1. States the problem with numbers (Cpk or PPM, or complaint counts and shares).
2. Recommends one action and estimates its benefit in dollars.
3. Says how you will know it worked (which chart, which rule, and what you would expect to see).

Include at least one chart from the app.

### Rubric (25 points)

| Criterion | Points |
|---|---|
| Stability checked before capability, and the reason explained | 4 |
| Capability indices and CIs correctly reported and interpreted | 6 |
| Centering vs spread diagnosis and the cost calculation | 5 |
| Pareto analysis, including the cost re-ranking | 5 |
| Proposal: clear, quantified, with a verification plan | 5 |
