# Lab 1: Is the filling line in control? (Variables control charts)

**Time:** about 60 minutes  **Tool:** QualityLab app (no coding)  **Deliverable:** a one-page memo plus two chart images

## Learning objectives

By the end of this lab you can:

1. Build and read an X̄-R chart, and explain why the R chart is checked first.
2. Separate a Phase I (limit-setting) study from Phase II (monitoring).
3. Tell common-cause from special-cause variation, and name the run rule behind each signal.
4. Explain why an EWMA or CUSUM chart can catch a slow drift sooner than an individuals chart.

## Setup

1. Open the app link your instructor posted.
2. In the sidebar choose **Practice scenario**, then **Cold-brew bottle fill volume**.
3. Under **Personal dataset code**, type the code your instructor gave you. *Your data are different from your classmates', so your answers will be too.*
4. Click **Download this dataset (CSV)** and keep it with your submission.

---

## Part A: The cold-brew filling line (X̄-R chart)

*A beverage plant fills 12-oz bottles. Every two hours, a technician pulls five consecutive bottles and records the fill. The specification is 11.88–12.12 oz. Management wants to know whether the line is "in control" and whether operators should adjust the filler.*

**A1.** On the **Control chart** tab, select **X̄-R**. Make sure **Phase I / Phase II** is checked with **15** points in Phase I. In your own words, what does it mean that the limits come from the first 15 samples only?

**A2.** Look at the **R chart** first. Does any sample show unusual *spread*? Give its number. Why must the R chart be in control before the X̄ chart's limits can be trusted? (Hint: look at how the X̄ limits are calculated.)

**A3.** Suppose the technician's log says the filling nozzle was found loose at that sample's time and has been tightened. Add that sample to **Exclude points from the limits**. What happened to the X̄ chart's UCL and LCL? Why?

**A4.** In Phase II, at which sample does the X̄ chart **first** signal, and under which rule? Copy the app's plain-language explanation and say whether you agree with it.

**A5.** Rules 5 and 6 can fire before any point crosses a control limit. Using your chart, explain to a production supervisor why it is worth reacting to "2 of 3 points beyond 2σ".

**A6.** Control limits and specification limits are different things. The process could be "in control" and still make out-of-spec bottles, or "out of control" while every bottle is in spec. Using numbers from your chart, explain which situation you are in.

## Part B: The call center (individuals, EWMA and CUSUM charts)

Switch the scenario to **Call-center average wait** (keep your personal code).

*A bank records the average wait before a caller reaches an agent, once per business day. Staffing changes were made at some point during these 60 days.*

**B1.** Build an **I-MR** chart with the first **30** days as Phase I and **Limits only (rule 1)** as the rule set. On which day, if any, does it first signal?

**B2.** Switch to **EWMA** (λ = 0.2) and then **CUSUM** (k = 0.5, h = 5). On which day does each first signal? For the CUSUM, the app estimates when the shift *began*. What day does it give?

**B3.** Now go back to the I-MR chart and switch to **Nelson / Minitab (all 8 tests)**. Does it signal sooner? Is there a catch? (Look at Phase I for any signals that are probably false alarms.)

**B4.** Open the **Which chart is fastest?** tab. Set the shift to 0.5σ, then 1σ, then 2σ, and record the average run length of each chart. Fill in the table:

| Shift | Shewhart | EWMA | CUSUM |
|---|---|---|---|
| 0 (false alarms) | | | |
| 0.5σ | | | |
| 1σ | | | |
| 2σ | | | |

Based on your table, when would you recommend a plain individuals chart and when an EWMA or CUSUM?

## Deliverable: memo to the operations manager (one page)

Write to the manager of the filling line (Part A). Include:

* Is the line in statistical control? Give the evidence: the chart, the rule(s) and the sample numbers.
* What most likely happened, and roughly when.
* What the operators should **and should not** do. Explain why adjusting the filler after every sample (tampering) would make things worse.
* One recommendation about the monitoring itself: sampling frequency, rules, or chart type.

Attach the X̄-R chart PNG and your downloaded dataset.

### Rubric (20 points)

| Criterion | Points |
|---|---|
| Correct signals identified (sample numbers and rules) | 6 |
| R chart checked before X̄, and the reason explained | 3 |
| Correct use of Phase I / II and of point exclusion | 3 |
| Control limits clearly separated from specification limits | 3 |
| Actionable, non-tampering recommendation | 3 |
| Clear, professional memo | 2 |
