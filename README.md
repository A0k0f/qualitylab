# QualityLab

**Decide how to watch a process before problems reach your customers. Then run the charts that do the watching.**

[![tests](https://github.com/A0k0f/qualitylab/actions/workflows/ci.yml/badge.svg)](https://github.com/A0k0f/qualitylab/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

Every operation, from a filling line to a warehouse or an accounts-payable team, faces the same nagging questions: *How often should we check? Is our audit catching anything, or just raising false alarms? Should we inspect everything, sample lots, or neither? Is a new machine worth it?* QualityLab answers them with numbers you can take to a meeting.

It has four parts:

* **🧭 Decision Studio (for managers).** Describe a process in plain terms: volume, what goes wrong and how often, what mistakes cost, how you check today. A Monte Carlo simulator replays years of operation under hundreds of monitoring and inspection plans. It recommends the cheapest plan that meets your limits (and a simpler one that is nearly as cheap), with the expected saving and its range. It also tests whether the answer survives if your estimates are off, finds the best process aim (overfill vs. out-of-spec), and prices improvement investments. Six editable industry scenarios are included.
* **📈 SPC Toolkit (for analysts and classes).** Upload data or open a practice scenario and get the right control chart (X̄-R, X̄-S, I-MR, p, np, c, u, Laney p′/u′, EWMA, CUSUM, Hotelling T²) with all eight run rules, capability with confidence intervals, and Pareto, each with a plain-language reading.
* **A tested Python library** behind both (about 100 tests), validated against textbook tables and published run-length results.
* **A case study on real fab data** ([SECOM](case_studies/secom/)). It asks whether SPC or machine learning, monitoring 590 sensors, can flag failing wafers, using a leakage-free, time-ordered design.

## Decision Studio

![Decision Studio results for the beverage filling line](docs/img/studio_results.png)

*Beverage filling line scenario.* Today a technician checks 5 bottles every 4 hours and reacts only if one is out of spec. The simulator recommends checking 2 bottles every 2 hours on a control chart. The expected saving is **≈ $85k a year** (between $45k and $125k in 8 of 10 simulated years). Problems get fixed after 4 hours instead of 13.5, and out-of-spec bottles reaching retailers drop from about 6,000 to about 1,000 per million. Aiming the filler at 12.045 oz instead of 12.10 is worth another ≈ $33k a year in product no longer given away.

| Question a manager has | What the studio shows |
|---|---|
| How often, how many, and what rule? | Cheapest plan among ~120–270 monitoring designs × up to 8 final-inspection options, under your limits on escapes and false alarms |
| Is the audit worth its cost? | Full cost breakdown: checks, false alarms, fixes, scrap, inspection, overfill, defects reaching customers |
| Inspect everything, sample lots, or neither? | 100 % inspection and lot sampling (with OC math) evaluated alongside monitoring |
| What if my numbers are wrong? | Tornado chart: savings and regret with each input at ½× and 1.5× |
| Where should we aim the process? | Cost curve of overfill vs. out-of-spec risk, with the optimum |
| Is the new machine / training / supplier program worth it? | Net annual benefit and payback per investment, re-optimizing the plan for each |
| How do I show my boss? | One-click HTML decision brief, Excel results, saved scenario files |

The engine (`qualitylab.simulate`) is validated against theory: in-control defect rates match closed forms exactly; false-alarm rates and detection delays match Shewhart ARLs; re-aiming after every check reproduces Deming's funnel (variance doubles); lot acceptance matches the binomial OC curve. See `tests/test_simulate.py`.

```python
from qualitylab.scenarios import templates
from qualitylab.decide import optimize, explain

t = templates()["filling"]                       # or build your own Process(...)
d = optimize(t.process, t.current, max_false_alarms_per_week=3)
print("\n".join(explain(d)))
```

## SPC Toolkit

![X̄-R chart of the cold-brew fill scenario](docs/img/xbar_r.png)

*Limits come from the first 15 samples. The R chart flags sample 9 (one subgroup with a much wider spread), which is excluded and the limits revised. From sample 20 the X̄ chart picks up a sustained upward shift in fill volume, through run rules 5 and 6 before any point crosses a limit. Numbers above points name the rule that fired.*

---

## Why another SPC package?

| | QualityLab |
|---|---|
| **Correct constants** | d2 and d3 come from exact numerical integration of the range distribution (not copied tables), and are checked against Montgomery's Appendix VI and against Monte Carlo |
| **Validated behavior** | Simulated ARLs match the literature: Shewhart 370.4; EWMA (λ=0.2, L=2.962) ≈ 500; CUSUM (k=0.5, h=5) ≈ 465; Western Electric rules ≈ 91.75 |
| **Real-world features** | Unequal subgroup sizes, Laney p′/u′ for huge samples, Phase I/II with excluded points and automatic revision, known-standard limits, one-sided specs |
| **Explains itself** | Every chart can describe its signals in plain language (`qualitylab.interpret.explain`) |
| **Built for teaching** | Seeded business scenarios, so each student gets a different dataset with a known answer key; four ready-to-run [labs](labs/) |

## Install

```bash
git clone https://github.com/A0k0f/qualitylab.git
cd qualitylab
pip install -e ".[app]"          # library + web app (Decision Studio + SPC Toolkit)
streamlit run app/streamlit_app.py
```

Or use the **[hosted app](https://YOUR-APP.streamlit.app)** (no install).

## Library quick start

```python
import qualitylab as ql

df = ql.datasets.load("coffee_fill")               # 30 samples × 5 bottles
xbar, r = ql.xbar_r(df.filter(like="bottle"), phase1=15, revise=True)
print(xbar.summary())
xbar.plot()

# attribute data with varying sample sizes; Laney adjustment for huge samples
orders = ql.datasets.load("online_orders")
ql.p_chart(orders.orders_returned, orders.orders_shipped, laney=True).summary()

# capability, with confidence intervals and a plain-language reading
cap = ql.capability(ql.datasets.load("shaft_diameter"), lsl=24.95, usl=25.05)
print(cap.to_frame())
print(cap.interpretation())

# how fast does each chart catch a 1σ shift?
ql.arl.compare(shifts=[0, 0.5, 1, 2])
```

```text
Xbar chart: 30 points, limits from 14 (Phase I = first 15, 1 excluded)
  CL = 12.0064
  UCL = 12.057   LCL = 11.9557
  Rule 1 (point beyond a control limit): 23, 25, 26, 30
  Rule 2 (run of points on one side of the center line): 27, 28, 29, 30
  ...
```

| Function | What it does |
|---|---|
| `xbar_r`, `xbar_s`, `imr` | Variables charts; return (location, dispersion) results |
| `p_chart`, `np_chart`, `c_chart`, `u_chart` | Attributes charts; `laney=True` for p′ / u′ |
| `ewma`, `cusum` | Time-weighted charts for small, sustained shifts |
| `hotelling_t2` | Multivariate T² (Phase I beta / Phase II F limits; sample or successive-difference covariance) |
| `capability` | Cp, Cpk, Pp, Ppk, Cpm, CIs, PPM (observed / within / overall), normality test, Z.bench |
| `pareto` | Sorted frequencies, cumulative share, "vital few" |
| `rules.evaluate` | Nelson rules 1–8 on any series (presets: `nelson`, `western_electric`, `attribute`, `limits`) |
| `arl` | Exact and simulated run-length distributions |
| `datasets` | Nine seeded business scenarios, with answer keys |
| `simulate` | What-if engine: processes, failure modes, monitoring & inspection policies, Monte Carlo costs |
| `decide` | Plan optimizer, robustness (sensitivity), process aim, investment ROI, calibration from data |
| `scenarios` | Six editable industry templates for the Decision Studio |

Every chart returns a `ChartResult` with `.statistic`, `.center`, `.ucl`, `.lcl`, `.violations`, `.to_frame()`, `.summary()` and `.plot()`.

## The SPC Toolkit app

| Control chart with interpretation | Which chart is fastest? |
|---|---|
| ![](docs/img/app_control_chart.png) | ![](docs/img/app_arl.png) |

* **Practice scenarios:** cold-brew filling, call-center waits, invoice errors, e-commerce returns, circuit-board defects, hotel complaints, complaint reasons, shaft diameters and a bottling line. Each comes with a story and a suggested tool.
* **Personal dataset code:** typing a code gives a student their own version of a scenario, so answers can't be copied.
* **Upload your own CSV/Excel:** wide or long subgroup layouts and attribute data are supported. Files are processed in the session only.
* **Exports:** charts as PNG, results as Excel.
* **ARL simulator:** shows why EWMA and CUSUM beat a Shewhart chart on small shifts, and what supplementary run rules cost in false alarms.

## Case study: SECOM semiconductor fab

> At a fixed 5% false-alarm budget, a per-sensor control chart caught 18% of failing wafers in a later period, ahead of Hotelling T², Isolation Forest and a supervised classifier. None of the methods was reliably better than chance. The monitoring did reveal a process change in late September that left yield unaffected.

[Read the full case study →](case_studies/secom/)

## Testing

```bash
pip install -e ".[dev]"
pytest -m "not slow"   # ~95 fast tests
pytest -m slow         # Monte Carlo ARL checks against published values
```

## Project layout

```text
src/qualitylab/     library (charts, rules, capability, multivariate, ARL, datasets, simulate, decide, plotting)
app/                Streamlit app: Home, Decision Studio, SPC Toolkit
case_studies/secom/ real-data case study
labs/               four classroom labs built on the app
tests/              unit and validation tests
scripts/            regenerates the d2/d3 constants table
```

## References

* Montgomery, D. C. *Introduction to Statistical Quality Control* (8th ed.). Wiley.
* Nelson, L. S. (1984). The Shewhart control chart: tests for special causes. *Journal of Quality Technology* 16(4).
* Lucas, J. M. & Saccucci, M. S. (1990). Exponentially weighted moving average control schemes. *Technometrics* 32(1).
* Laney, D. B. (2002). Improved control charts for attributes. *Quality Engineering* 14(4).
* Sullivan, J. H. & Woodall, W. H. (1996). A comparison of multivariate control charts for individual observations. *Journal of Quality Technology* 28(4).
* Champ, C. W. & Woodall, W. H. (1987). Exact results for Shewhart control charts with supplementary runs rules. *Technometrics* 29(4).
* Lorenzen, T. J. & Vance, L. C. (1986). The economic design of control charts: a unified approach. *Technometrics* 28(1).
* Schilling, E. G. & Neubauer, D. V. *Acceptance Sampling in Quality Control*. CRC Press.

## License

MIT © 2026 Ali Karamifard. Practice datasets are simulated. SECOM data © the original authors, CC BY 4.0, downloaded at run time.
