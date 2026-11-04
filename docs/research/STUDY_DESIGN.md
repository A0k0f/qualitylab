# Study design: learning quality management with interactive simulations

A ready-to-adapt design for a classroom study built on the Learning Lab. It is written for a senior undergraduate course in managing quality (e.g., POM 445), but nothing in it is specific to one university. Adapt it to your IRB's forms. The headings follow what most IRB applications and an eventual paper both need.

## Background

Undergraduate business students often learn statistical process control and Deming's management philosophy as definitions to memorise. Classic misconceptions persist after instruction: blaming individuals for system variation, adjusting a stable process after every measurement (tampering), confusing control limits with specification limits, and treating inspection as a substitute for capability. Physical simulations such as Deming's red bead experiment and Nelson's funnel are known to confront these misconceptions, but they take class time, run once, and leave no individual record of what each student believed.

The centre of the Learning Lab is the **Process Lab**, an open simulation environment. Each student defines a process (what is measured, target, specification limits, unit-to-unit variation, centring, sample size, costs), decides what goes wrong and when (sudden shifts, gradual drifts, increased variation, single outliers, or nothing), designs the monitoring (Shewhart, EWMA or CUSUM chart; run rules; limits estimated from a baseline or known; reacting to signals or not), predicts the outcome, and runs the experiment. The data, charts and outcomes are generated from the student's own settings with the validated QualityLab chart functions, so there is no fixed scenario and no answer key: each student's sequence of experiments is their own. Students can re-run a design with new random data, run it 200 times to see the distribution of outcomes, change one thing and run again, and write a note on what they learned.

This produces a rich, fully reproducible record of *how* novices experiment with a quality system: which factors they vary, whether they make controlled (one-factor) comparisons, whether they replicate before drawing conclusions, and whether their predictions about detection, false alarms and defects improve with experience. Each experiment follows a **predict → run → compare → explain** cycle, drawing on research showing that generating a prediction before seeing an outcome improves conceptual learning (e.g., Crouch et al., 2004; Brod, 2021) and on research on scientific reasoning and the control-of-variables strategy (Chen & Klahr, 1999; de Jong & van Joolingen, 1998).

Six short guided missions (Deming's red beads, signal-or-noise judgments, the funnel, capability, cost of quality, monitoring economics) are available as optional extras.

## Research questions

* **RQ1 (learning).** Do students' scores on a 12-item concept check about quality management improve from before to after the Learning Lab? Which misconceptions change most and which persist?
* **RQ2 (experimentation strategies).** How do business students experiment with a process-monitoring system? How many experiments do they run, which settings do they vary, how often do they make controlled one-factor comparisons, and how often do they replicate before concluding? Do these strategies relate to concept gains?
* **RQ3 (learning from experience).** Do students' predictions of detection, detection delay, false alarms and out-of-spec output become more accurate over successive experiments?
* **RQ4 (prediction).** Does asking students to predict before each run produce larger learning gains than the same activity without prediction? *(Optional randomised component.)*
* **RQ5 (guided missions, if used).** Within missions, do students' decisions improve with feedback (e.g., signal-detection d′ between two rounds; finding the cheapest way to meet a capability target; portfolio optimality)?
* **RQ6 (calibration).** How well does students' confidence match their accuracy, in the concept check and in their experiment predictions?
* **RQ7 (experience).** How usable do students find the tool (System Usability Scale), and what do they say helped or confused them?

## Design

Single-group pre/post design with process data from every experiment (RQ1–RQ3, RQ5–RQ7), with an optional embedded two-arm randomised comparison (RQ4).

* **Pre-test:** 12-item concept check with confidence ratings (warm-up, before any activity).
* **Intervention:** the Process Lab (open-ended; 30 to 45 minutes is a good class session), optionally followed by any of the six guided missions.
* **Post-test:** the same 12 items, in a different order.
* **Survey:** SUS (10 items), six learning items, two open questions.

**Randomisation (optional).** When `conditions = ["predict", "no_predict"]` is set, each participant is assigned by a hash of their anonymous code, so the assignment is effectively random, balanced on average, stable across sessions, and invisible to the researcher in advance. The `no_predict` condition skips every "predict first" step and the survey item about predicting; everything else is identical.

## Participants

Students enrolled in the course who are 18 or older and choose to take part. No exclusion beyond age. Typical section size gives 25 to 45 participants per semester; pooling sections and semesters (each tagged with its own `course_code`) increases power. With 40 participants, a paired design detects a within-person change of about d = 0.45 with 80 % power (α = .05, two-sided). The between-condition comparison needs roughly 64 per arm for d = 0.5, so plan RQ2 across several sections.

## Procedure

1. The instructor posts the app link. Students open **Learning Lab** in a browser.
2. The consent screen explains the study. Students tick "I am 18 or older" and choose **I agree** or **No thanks**. Both choices lead to the same activity.
3. Participants create an anonymous code from three questions only they can answer. The app shows them the resulting code (e.g., `P-3F9A0C12BD`) so they can withdraw later.
4. Warm-up check → Process Lab (and optional missions) → final check → feedback survey.
5. Students can download their own learning record at any time.

## Measures

| Measure | Source | Notes |
|---|---|---|
| Every experiment: full design, what changed since the previous one, goal, prediction, outcome, replication, note | Process Lab | One row per experiment (`experiments()`); every run is reproducible from its logged seed |
| Controlled comparisons | Process Lab | Share of follow-up experiments changing exactly one setting |
| Replication | Process Lab | Whether a design was run 200 times before moving on |
| Prediction accuracy over experiments | Process Lab | Detection correct; delay error abs(log(predicted / actual)), which does not depend on the size of the delay; false-alarm and out-of-spec errors |
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
* **RQ2:** descriptive statistics of the experiment table (experiments per student, settings varied, one-factor share, replication); sequence analysis of the `changed` field; correlation (or regression with pre-test as covariate) of one-factor share and replication with normalised gain.
* **RQ3:** prediction errors by experiment number (learning curve); paired comparison of each student's first and second half of experiments; a mixed-effects model with experiment number as fixed effect and student as random effect is the stronger analysis when n allows.
* **RQ4:** Welch t-test of gain and ANCOVA of post score on pre score and condition. Report the effect with a CI regardless of significance.
* **RQ5:** paired comparison of d′ between rounds; proportions finding the cheapest capability fix and the optimal portfolio; first vs. best attempt.
* **RQ6:** mean confidence on correct vs. incorrect answers and predictions.
* **RQ7:** SUS mean and distribution (68 is the usual benchmark); thematic coding of open responses and experiment notes by two coders.
* Missing data: analyses use all available participants per measure and report n for each. Participants with both checks form the RQ1 sample.

`scripts/analyze_learning_lab.py` writes the participant and experiment tables, runs the RQ1–RQ7 statistics and writes a short report.

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
* Chen, Z., & Klahr, D. (1999). All other things being equal: acquisition and transfer of the control of variables strategy. *Child Development* 70(5), 1098–1120.
* de Jong, T., & van Joolingen, W. R. (1998). Scientific discovery learning with computer simulations of conceptual domains. *Review of Educational Research* 68(2), 179–201.
* Hake, R. R. (1998). Interactive-engagement versus traditional methods. *American Journal of Physics* 66(1), 64–74.
* Hautus, M. J. (1995). Corrections for extreme proportions and their biasing effects on estimated values of d′. *Behavior Research Methods* 27(1), 46–51.
* Kapur, M. (2016). Examining productive failure, productive success, unproductive failure, and unproductive success in learning. *Educational Psychologist* 51(2), 289–299.
* Montgomery, D. C. *Introduction to Statistical Quality Control* (8th ed.). Wiley.
