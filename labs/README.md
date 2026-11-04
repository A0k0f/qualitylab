# Classroom labs

Materials for an undergraduate quality-management course (written for a senior-level business course on managing quality). Everything uses the QualityLab web app, so **students need no coding and no installation**: a browser is enough.

**Start with the [Learning Lab](learning_lab.md).** Six short missions (red beads, signal or noise, the funnel, capability, cost of quality, monitoring economics) build the intuition behind the course, with a concept check before and after. The guide covers schedules, debrief questions and an optional graded reflection.

Then the four labs build technical skill: Labs 1–3 use the **SPC Toolkit**; Lab 4 uses the **Decision Studio**.

| Lab | Topic | Scenarios | Deliverable |
|---|---|---|---|
| [Learning Lab](learning_lab.md) | Deming, common vs. special causes, tampering, capability, cost of quality, monitoring economics | Six missions | Optional one-page reflection |
| [Lab 1](lab1_variables_charts.md) | Variables charts, Phase I/II, run rules, EWMA/CUSUM | Cold-brew filling; call-center waits | Memo to an operations manager |
| [Lab 2](lab2_attribute_charts.md) | p, np, c, u charts; Laney p′; showing an improvement | Invoice errors; e-commerce returns; circuit boards; hotel complaints | Answers plus a recommendation |
| [Lab 3](lab3_capability_pareto.md) | Capability (Cp, Cpk, Pp, Ppk), Pareto | Machined shafts; cold-brew filling; complaint reasons | Improvement proposal |
| [Lab 4](lab4_decision_studio.md) | Economic design of monitoring, tampering, robustness, process aim, investments | Decision Studio: filling line + one industry scenario | Decision memo + brief |

## Personal datasets

Each student types a **dataset code** into the app and gets their own version of every scenario: the special causes fall at different points and with different sizes. Two students therefore cannot simply share answers, while the lessons stay the same.

Every generated dataset is checked automatically so that, with the settings the labs specify, the planted story is detectable and the reference period has no false alarms. These are teaching data; data from actual operations are messier, and the SECOM case study shows how much.

> **Privacy:** use codes that the instructor assigns (e.g. `QL-7F3K2`), not student ID numbers. The SPC Toolkit and Decision Studio never store anything students type or upload. Even so, assigned codes keep student identifiers out of the tool entirely. The Learning Lab stores nothing either, unless an instructor has turned on the optional [research kit](../docs/research/) and the student consents.

## Hosting the app for a class (free, about 10 minutes)

1. Push this repository to GitHub (public).
2. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub. Choose **Create app**, select the repository, set the main file to `app/streamlit_app.py`, and deploy.
   A Decision Studio search uses a few CPU-seconds per run; for a whole class running it at once, stagger the start or have students work in pairs.
3. Post the resulting `https://….streamlit.app` link on the course page.

Free-tier apps go to sleep after a period of inactivity; the first visitor wakes them in under a minute. Open the link a few minutes before class.

## Answer keys

Answer keys for Labs 1–3 are generated per dataset code with a separate instructor script, which is kept **out of this public repository**. If you are an instructor and want it, contact the author.
