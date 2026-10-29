# Lab 4: How should we watch this process? (Economic design with the Decision Studio)

**Time:** about 75 minutes  **Tool:** QualityLab → **Decision Studio**  **Deliverable:** a one-page decision memo plus the downloaded decision brief

## Learning objectives

1. Treat monitoring as a business decision: every check, false alarm, fix, scrapped unit and escaped defect has a price.
2. Explain why "check and react to every result" (tampering) makes a process worse.
3. Judge whether a recommendation is robust to uncertain inputs, and decide which number is worth measuring better.
4. Compare monitoring, inspection and process improvement as ways to spend the same money.

---

## Part A: The filling line

Open **Decision Studio** and start from **Beverage filling line**. Read the five input tabs before you change anything.

**A1.** In your own words, what are the three things that go wrong on this line, and how does each one hurt the business?

**A2.** Press **Simulate and recommend**. Record today's plan and the recommended plan, with their expected annual cost, hours until a problem is fixed, defects reaching customers (ppm) and false alarms per week.

**A3.** Today the technician checks 5 bottles every 4 hours and reacts only if a bottle is *out of spec*. Use the **See it happen** tab to explain why that rule is slow to catch a clogged nozzle. (Hint: where does the average sit relative to the LSL during a clog?)

**A4.** Open **Money**. Which cost category shrinks most under the recommendation? Which one grows? Why is that trade worth it?

**A5. Tampering.** In *Today's approach*, change the routine to **Re-aim the process after every check**, with 1 unit every hour. Simulate again. What happens to the cost and to defects reaching customers? Explain the result using Deming's funnel experiment.

## Part B: How sure are we?

Restore the template (choose another scenario, then back), simulate, and open **Robustness** → **Run robustness check**.

**B1.** Which input has the biggest effect on the savings? Which has almost none?

**B2.** Is there an input for which the recommendation could *lose* money or stop being the best plan? What data would you collect, and for how long, to pin that number down?

## Part C: Where to aim

Open **Process aim**.

**C1.** Where does the line run today, and where does the tool suggest aiming it? What is the annual saving?

**C2.** Lowering the fill target saves product but moves the process closer to the legal minimum. What else would you want to know before approving the change? Think about regulators, retailers and how stable the line really is.

## Part D: Another industry

Pick **one** of: *Warehouse order accuracy*, *Pharmacy dispensing safety* or *Incoming inspection of supplier lots*.

**D1.** What does the organization do today, and what does the tool recommend? Is the recommendation mainly about *monitoring* (catching problems early) or *inspection* (sorting good from bad before shipping)?

**D2.** Open **Investments** → **Evaluate investments**. Does any option pay for itself? Add one improvement idea of your own, with a realistic yearly cost, and evaluate it.

**D3.** Change one cost you think the template gets wrong (justify the new value) and re-run. Does the recommendation change?

## Deliverable: decision memo (one page)

Write to the manager of the process you chose in Part D:

* the recommendation and its expected annual saving (with the range)
* what operators will do differently on Monday morning
* how robust the recommendation is, and which input you would verify first
* whether an investment is worth pursuing

Attach the **Decision brief (HTML)** from the *Download* tab, printed to PDF.

### Rubric (25 points)

| Criterion | Points |
|---|---|
| Correct reading of costs, detection time, escapes and false alarms (A2–A4) | 6 |
| Tampering explained with evidence (A5) | 4 |
| Robustness interpreted, with a concrete data-collection plan (B) | 5 |
| Aim decision with business and compliance judgment (C) | 4 |
| Memo: clear, quantified, actionable | 6 |
