# Study design: learning quality management with interactive simulations

A ready-to-adapt design for a classroom study built on the Learning Lab. It is written for a senior undergraduate course in managing quality (e.g., POM 445), but nothing in it is specific to one university. Adapt it to your IRB's forms. The headings follow what most IRB applications and an eventual paper both need.

## Background

Undergraduate business students often learn statistical process control and Deming's management philosophy as definitions to memorise. Classic misconceptions persist after instruction: blaming individuals for system variation, adjusting a stable process after every measurement (tampering), confusing control limits with specification limits, and treating inspection as a substitute for capability. Physical simulations such as Deming's red bead experiment and Nelson's funnel are known to confront these misconceptions, but they take class time, run once, and leave no individual record of what each student believed.

The Learning Lab turns six of these classic demonstrations into short, individual "missions" in which students make management decisions, see the consequences, and explain them. Each mission follows a **predict → decide → observe → explain** cycle. The predict step draws on research showing that generating a prediction before seeing an outcome improves conceptual learning (e.g., Crouch et al., 2004; Brod, 2021; Kapur, 2016 on productive failure).

## Research questions

* **RQ1 (learning).** Do students' scores on a 12-item concept check about quality management improve from before to after the Learning Lab? Which misconceptions change most and which persist?
* **RQ2 (prediction).** Does asking students to predict before seeing each result produce larger learning gains than the same missions without prediction? *(Optional randomised component.)*
* **RQ3 (decision quality).** Within missions, do students' decisions improve with feedback? For example: does their ability to tell signals from noise on control charts (d′) improve between the first and second round of eight charts; do they find the cheapest way to meet a capability target; how close do their project portfolios get to the optimal one?
* **RQ4 (calibration).** How well does students' confidence match their accuracy before and after?
* **RQ5 (experience).** How usable do students find the tool (System Usability Scale), and what do they say helped or confused them?

## Design

Single-group pre/post design (RQ1, RQ3–RQ5), with an optional embedded two-arm randomised comparison (RQ2).

* **Pre-test:** 12-item concept check with confidence ratings (warm-up, before any mission).
* **Intervention:** six missions, any order, about 60 to 75 minutes in total.
* **Post-test:** the same 12 items, in a different order.
* **Survey:** SUS (10 items), six learning items, two open questions.

**Randomisation (optional).** When `conditions = ["predict", "no_predict"]` is set, each participant is assigned by a hash of their anonymous code, so the assignment is effectively random, balanced on average, stable across sessions, and invisible to the researcher in advance. The `no_predict` condition skips every "predict first" step and the survey item about predicting; everything else is identical.

## Participants

Students enrolled in the course who are 18 or older and choose to take part. No exclusion beyond age. Typical section size gives 25 to 45 participants per semester; pooling sections and semesters (each tagged with its own `course_code`) increases power. With 40 participants, a paired design detects a within-person change of about d = 0.45 with 80 % power (α = .05, two-sided). The between-condition comparison needs roughly 64 per arm for d = 0.5, so plan RQ2 across several sections.

## Procedure

1. The instructor posts the app link. Students open **Learning Lab** in a browser.
2. The consent screen explains the study. Students tick "I am 18 or older" and choose **I agree** or **No thanks**. Both choices lead to the same activity.
3. Participants create an anonymous code from three questions only they can answer. The app shows them the resulting code (e.g., `P-3F9A0C12BD`) so they can withdraw later.
4. Warm-up check → missions → final check → feedback survey.
5. Students can download their own learning record at any time.

## Measures

| Measure | Source | Notes |
|---|---|---|
| Concept score (0–1), per item correct, confidence 1–5 | Pre and post checks | 12 items mapped to course objectives; see `src/qualitylab/learn/concepts.py` |
| Normalised gain ⟨g⟩ = (post − pre)/(1 − pre) | Derived | Hake (1998) |
| System-cause attribution | Red beads, "why" question | Correct = the system (the bead mix), not the workers |
| Blame index | Red beads | Share of Day 1 actions that rewarded or punished individuals |
| Chose the system fix | Red beads | Supplier change is the only option that lowers the red share |
| Signal detection d′, hits, false alarms, accuracy | Signal or Noise, rounds A and B | 8 charts each; ground truth defined by Western Electric rules 1, 2 (8 in a row), 3, 5, 6; log-linear correction (Hautus, 1995) |
| Tampering slope and SD ratio | Funnel | Slope of adjustment on previous deviation (−1 = full compensation); spread vs. leaving the process alone |
| Capability decisions | Keep the Customer | Number of attempts; found the cheapest combination that achieves Cpk ≥ 1.33 |
| Cost-of-quality classification | Where Does the Money Go? | 8 items, 2 per category |
| Portfolio quality | Where Does the Money Go? | Annual saving of chosen projects as a share of the exact optimum (knapsack) |
| Plan regret | Be the Quality Manager | Extra annual cost of the chosen plan over the best of 32 simulated plans |
| Prediction accuracy | All missions (predict condition) | |
| Time on task | All steps | Seconds per step and minutes per mission |
| SUS (0–100) | Survey | Brooke (1996) |
| Perceived learning L1–L6 (1–5) | Survey | L2 asked only in the predict condition |
| Open responses | Survey and mission reflections | Thematic analysis |

All measures are produced automatically by `qualitylab.research_analysis.participants()`.

## Analysis plan

* **RQ1:** paired t-test of pre vs. post score, with Wilcoxon signed-rank as a check; Cohen's d_z with 95 % CI; class and mean individual normalised gain. Item-level McNemar-style comparison of the share correct before and after (reported descriptively for 12 items).
* **RQ2:** Welch t-test of gain (or ANCOVA of post score on pre score and condition) between conditions. Report the effect with a CI regardless of significance.
* **RQ3:** paired comparison of d′ between rounds A and B; proportions finding the cheapest capability fix and the optimal portfolio; first vs. best attempt.
* **RQ4:** mean confidence on correct vs. incorrect items, pre and post.
* **RQ5:** SUS mean and distribution (68 is the usual benchmark); thematic coding of open responses by two coders.
* Missing data: analyses use all available participants per measure and report n for each. Participants with both checks form the RQ1 sample.

`scripts/analyze_learning_lab.py` runs the RQ1–RQ3 and RQ5 statistics and writes a short report.

## Risks, privacy and the dual role of the instructor

* Minimal risk: the activity is part of normal coursework.
* No direct identifiers are collected; see [SETUP.md](SETUP.md#how-the-privacy-protections-work).
* Participation has no effect on grades. Completing the Learning Lab itself may be assigned as coursework, but **consenting to research is separate from the activity** and never required.
* Because the instructor is also a researcher, the default consent text states that nobody will look at individual responses until final grades have been submitted, and that class-level, anonymous summaries may be shown in class. Change `data_access_note` if your IRB asks for a different arrangement.
* Withdrawal: a participant emails their code; all rows with that code are deleted.
* Data are stored on IRB-approved university storage and kept for the period your institution requires.

## Ethical and practical notes

* Some IRBs classify studies of normal educational practice with de-identified data as exempt (US 45 CFR 46.104(d)(1)). That decision belongs to the IRB, not the researcher.
* Pilot the full Learning Lab yourself before the term and time it.
* Keep the same app version for a whole study. The `app_version` column records it.

## References

* Brooke, J. (1996). SUS: a "quick and dirty" usability scale. In *Usability Evaluation in Industry*. Taylor & Francis.
* Brod, G. (2021). Generative learning: which strategies for what age? *Educational Psychology Review* 33, 1295–1318.
* Crouch, C. H., Fagen, A. P., Callan, J. P., & Mazur, E. (2004). Classroom demonstrations: learning tools or entertainment? *American Journal of Physics* 72(6), 835–838.
* Deming, W. E. (1986). *Out of the Crisis*. MIT Press.
* Goetsch, D. L., & Davis, S. B. *Quality Management for Organizational Excellence: Introduction to Total Quality* (9th ed.). Pearson.
* Hake, R. R. (1998). Interactive-engagement versus traditional methods. *American Journal of Physics* 66(1), 64–74.
* Hautus, M. J. (1995). Corrections for extreme proportions and their biasing effects on estimated values of d′. *Behavior Research Methods* 27(1), 46–51.
* Kapur, M. (2016). Examining productive failure, productive success, unproductive failure, and unproductive success in learning. *Educational Psychologist* 51(2), 289–299.
* Montgomery, D. C. *Introduction to Statistical Quality Control* (8th ed.). Wiley.
