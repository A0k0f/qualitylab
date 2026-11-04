# Data dictionary

## Raw events (one row per event)

This is the layout of the `events` tab in the Google Sheet, of `events.jsonl` in local mode, and of the raw CSV export on the Instructor page. Defined in `qualitylab.research.FIELDS`.

| Column | Type | Meaning |
|---|---|---|
| `event_id` | text | Random unique ID of the row (duplicates from network retries are dropped in analysis) |
| `ts_utc` | ISO time | When the event happened, UTC, millisecond precision |
| `session_id` | text | Random ID of one browser session. A student who returns another day gets a new session ID but the same `participant_id` |
| `participant_id` | text | Anonymous code `P-` + 10 hex characters (salted SHA-256 of the three self-generated answers) |
| `condition` | text | Experimental condition (`predict`, `no_predict`), empty if no experiment is configured |
| `course_code` | text | From the app settings, e.g. `POM445-SP27-01` |
| `app_version` | text | QualityLab version that produced the row |
| `mission` | text | `consent`, `concept`, `processlab`, `redbeads`, `signals`, `funnel`, `capability`, `pareto`, `manager`, `survey` |
| `step` | text | Step within the mission (see below) |
| `event_type` | text | `consent`, `start`, `answer`, `prediction`, `decision`, `result`, `replicate`, `score`, `text`, `complete` |
| `item_id` | text | Question or chart ID, when the event is about one item |
| `response` | JSON text | What the student chose or typed (a number, a label, a list or an object) |
| `correct` | 0/1 | Whether the response was correct, where there is a right answer |
| `confidence` | 1–5 | Self-rated confidence (1 = guessing, 5 = certain), where asked |
| `score` | number | Event-specific score (see below) |
| `latency_s` | seconds | Time from the step being shown to the response; for `complete`, minutes on the mission × 60 |
| `detail` | JSON text | Context needed to interpret the event (e.g. the chart's ground truth) |

## Events by mission

| mission | step | event_type | item_id | response · correct · score · detail |
|---|---|---|---|---|
| consent | consent | consent | | `{"agreed": true, "adult": true}` |
| *any mission* | start / end | start / complete | | `complete`: response = mission summary, score = mission score, latency_s = time on mission |
| concept | pre / post | answer | C01–C12 | response = option index chosen (0-based) · correct · confidence |
| concept | pre / post | score | | score = share correct (0–1) · latency_s = time on the whole check |
| redbeads | day1, day2 | decision | | response = action per worker · detail = that day's red-bead counts |
| redbeads | predict_day2 | prediction | | response = predicted best worker and team total · correct = best worker right · score = absolute error of the total |
| redbeads | why | answer | RB_WHY | correct = attributed differences to the system · confidence |
| redbeads | reveal | result | | score = blame index (share of actions aimed at individuals) · detail = control limits and points beyond them |
| redbeads | system_change | decision | | response = change chosen · correct = supplier (the only change that alters the system) · detail = red beads made and shipped per day afterwards |
| redbeads | predict_change | prediction | | response = predicted reds per day after the change · score = absolute error · detail = actual value |
| redbeads | reflect | text | RB_CEO | written answer |
| signals | phaseA / phaseB | decision | chart ID | response = investigate or not · correct · confidence · score = payoff ($) · detail = category, whether it was a signal, kind, start point, business context, rules that fire, zones shown |
| signals | phaseA / phaseB | score | | score = d′ for the round · response = hit and false-alarm rates, hits, false alarms, accuracy, money won or lost, false alarms on tempting noise charts, hits on subtle signals |
| signals | reflect | text | SIG_INSIDE | written answer |
| funnel | predict_adjust | prediction | | response = option chosen (2 = adjusting makes it worse) · correct · confidence |
| funnel | play | result | | score = spread of the student's fills ÷ spread if left alone · detail = tampering slope, share of fills adjusted, adjustments |
| funnel | predict_rule | prediction | | response = strategy predicted best (1–4) · correct = strategy 1 |
| funnel | check | answer | FN_BARISTA | transfer question · correct · confidence |
| funnel | reflect | text | FN_EXAMPLE | written answer |
| capability | predict_ppm / predict_capable | prediction | | predicted share out of spec; predicted whether the process is capable · correct · confidence |
| capability | sort | answer | QA_control … QD_capable | classification of four processes A–D (in control? capable?) · correct |
| capability | attempt1, attempt2, … | decision | | response = actions chosen · correct = meets Cpk ≥ 1.33 at the lowest possible cost · score = Cpk achieved · detail = cost, whether the target is met, cheapest possible cost |
| capability | check | answer | CAP_INSPECT | transfer question on inspection vs. capability · correct · confidence |
| capability | reflect | text | CAP_EXPLAIN | written answer |
| pareto | coq | answer | COQ1–COQ8 | category chosen for each cost item · correct |
| pareto | coq | score | | share of the 8 items classified correctly |
| pareto | predict_top | prediction | | complaint predicted to cost most · correct |
| pareto | attempt1, … | decision | | response = projects funded · correct = optimal portfolio · score = annual saving ÷ optimal saving · detail = cost, saving, optimal saving |
| pareto | reflect | text | PG_CFO | written answer |
| manager | predict_best | prediction | | response = predicted lowest annual cost · score = (prediction − true best) ÷ true best |
| manager | attempt1, … | decision | | response = plan (how often, sample size, rule, final inspection) · correct = the best plan · score = regret (extra cost over the best plan, as a share) · detail = annual cost, rank among the 32 plans |
| manager | reflect | text | MG_WHYNOT | written answer |
| survey | sus | answer / score | SUS1–SUS10 | response 1–5 per item; score = SUS 0–100 (only when all 10 answered) |
| survey | learning | answer | L1–L6 | response 1–5 (L2 only in the `predict` condition) |
| survey | open | text | most_helpful, improve | written answers |
| processlab | example | decision | | example the student loaded as a starting point (optional) |
| processlab | exp1, exp2, … | decision | | **the full experiment design** (response: process, changes, monitoring settings as JSON) · latency_s = time spent setting it up · detail = `kind` (`new` or `rerun` with new random data), `changed` (settings that differ from the previous experiment), `n_changed`, `goal`, `goal_text`, `seed` (reproduces the exact run) |
| processlab | exp1, … | prediction | | response = predicted detection (Yes/No), delay, false alarms, out-of-spec %, reasoning · confidence · correct = detection prediction right · score = delay error in samples · detail = all prediction errors, incl. `delay_log_error` = abs(log(predicted / actual delay)) |
| processlab | exp1, … | result | | response = outcome of the run: per change (detected, delay, signal sample, fixed), false alarms, monitored quiet samples, investigations, out-of-spec share, costs, capability (estimated and true) · score = total cost |
| processlab | exp1, … | replicate | | the same design run 200 times: share of runs catching each change, median and mean delay, false alarms per 100 quiet samples, mean cost and 10th–90th percentile |
| processlab | exp1, … | text | PL_REFLECT | the student's note on that experiment |

In the `no_predict` condition no `prediction` events exist.

## Experiment table (one row per Process Lab experiment)

Produced by `qualitylab.research_analysis.experiments(events)`, the Instructor page ("Experiments (CSV)") and `experiments.csv` from the analysis script. This is the main dataset for studying *how students experiment*.

| Column | Meaning |
|---|---|
| `participant_id`, `condition`, `course_code`, `session_id`, `exp`, `ts_utc` | Who, which condition, when; `exp` is the experiment number within the session |
| `kind` | `new` (student pressed Run after possibly changing settings) or `rerun` (same settings, new random data) |
| `goal` | What the student said they were trying to find out (`explore`, `fast`, `few_alarms`, `low_oos`, `cheap`, `own`) |
| `changed`, `n_changed` | Settings that differ from the previous experiment (e.g. `process.n;monitor.chart`) and how many. `n_changed = 1` is a controlled, one-factor comparison |
| `setup_seconds` | Time spent designing the experiment |
| `chart`, `rules`, `limits_from`, `react` | Monitoring design |
| `n`, `samples`, `baseline`, `sigma`, `target`, `lsl`, `usl`, `off_center` | Process design |
| `n_process_changes`, `change_kinds`, `first_change_kind`, `first_change_at`, `first_change_size_sigma`, `first_change_in_baseline` | What the student made go wrong (size in σ of one unit) |
| `pred_detect`, `pred_delay`, `pred_false_alarms`, `pred_oos_pct`, `pred_confidence`, `pred_why` | The prediction |
| `pred_detect_correct`, `pred_delay_abs_error`, `pred_delay_log_error`, `pred_false_alarm_abs_error`, `pred_oos_abs_error` | How far off it was |
| `detected`, `delay`, `false_alarms`, `quiet_samples`, `investigations`, `oos_share`, `cost_total`, `true_cpk` | Outcome (for the first change) |
| `replicated`, `rep_detect_rate`, `rep_delay_median`, `rep_false_alarms_per_100` | Whether the student ran it 200 times, and what that showed |
| `reflection` | The student's note |

Every run is reproducible: `Experiment.from_dict(design)` with the logged `seed` in `qualitylab.learn.process_lab.run` regenerates the exact data the student saw.

## Participant table (one row per student)

Produced by `qualitylab.research_analysis.participants(events)`, the Instructor page's Excel export, and `participants.csv` from the analysis script.

| Column | Meaning |
|---|---|
| `condition`, `course_code`, `sessions`, `first_seen`, `last_seen`, `events` | Bookkeeping |
| `pre_score`, `post_score` | Concept check, share correct (0–1). Pre = first attempt, post = last attempt |
| `pre_confidence`, `post_confidence` | Mean confidence over the 12 items |
| `gain`, `normalized_gain` | post − pre; (post − pre) ÷ (1 − pre) |
| `<mission>_done`, `<mission>_minutes` | Completed the mission; minutes spent |
| `rb_system_cause` | Red beads: attributed the variation to the system |
| `rb_blame_index` | Red beads: share of Day 1 actions that rewarded or punished individuals (0 = none) |
| `rb_chose_supplier` | Red beads: chose the only change that improves the system |
| `sig_dprime_A`, `sig_dprime_B` | Signal detection sensitivity in rounds 1 and 2 (0 = chance; > 2 = very good) |
| `sig_accuracy_*`, `sig_hits_*`, `sig_false_alarms_*` | Round accuracy, number of real signals investigated, number of noise charts investigated |
| `fn_sd_ratio` | Funnel: student's spread ÷ spread with no adjustment (> 1 = tampering made it worse) |
| `fn_tamper_slope` | Funnel: slope of adjustment on the last deviation (−1 = full compensation, 0 = no reaction) |
| `fn_share_adjusted` | Funnel: share of fills after which the student changed the aim |
| `fn_check_correct` | Funnel transfer question |
| `cap_attempts`, `cap_found_cheapest`, `cap_sort_score` | Capability: attempts; reached the cheapest solution; four-process sort (0–8) |
| `pg_coq_score` | Cost-of-quality classification (0–1) |
| `pg_first_share_of_optimal`, `pg_best_share_of_optimal` | Project portfolio: first and best attempt as a share of the optimal saving |
| `mg_first_regret_pct`, `mg_best_regret_pct` | Monitoring plan: extra cost over the best plan, first and best attempt |
| `pl_experiments`, `pl_new`, `pl_reruns`, `pl_replications`, `pl_notes` | Process Lab activity |
| `pl_one_factor_share` | Share of follow-up experiments that changed exactly one setting |
| `pl_factors_explored`, `pl_charts_tried` | Number of different settings varied; number of chart types used |
| `pl_detect_acc_first_half`, `pl_detect_acc_second_half` | Detection predictions correct, first vs. second half of the student's experiments |
| `pl_delay_err_first_half`, `pl_delay_err_second_half` | Delay prediction error abs(log(predicted / actual)), first vs. second half |
| `pl_fa_err_first_half`, `pl_fa_err_second_half` | False-alarm prediction error, first vs. second half |
| `predictions_made`, `prediction_accuracy` | Number of predictions; share correct (where a prediction can be right or wrong) |
| `sus` | System Usability Scale, 0–100 |
| `L1`–`L6` | Perceived learning items, 1–5 |

## Concept check items

| ID | Concept | Course objective |
|---|---|---|
| C01 | Common vs. special causes | Problem-solving methods |
| C02 | Control limits vs. specification limits | SPC |
| C03 | Statistical control | SPC |
| C04 | Tampering | TQM philosophy (Deming) |
| C05 | Deming and the system | TQM philosophy (Deming) |
| C06 | Cp vs. Cpk | SPC |
| C07 | Run rules | SPC |
| C08 | Pareto analysis | Problem-solving methods |
| C09 | Cost of quality | Quality as competitive strategy |
| C10 | Inspection vs. capability | Decision-making for quality improvement |
| C11 | Regression to the mean | Decision-making for quality improvement |
| C12 | Economics of monitoring | Decision-making for quality improvement |

The question wording, options and explanations are in `src/qualitylab/learn/concepts.py`. Questions appear in a different order in the pre and post checks.
