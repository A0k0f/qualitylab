"""Analyse Learning Lab research data.

Usage
-----
    python scripts/analyze_learning_lab.py events.csv --out results/
    python scripts/analyze_learning_lab.py events.jsonl --course POM445-SP27-01 --out results/
    python scripts/analyze_learning_lab.py --synthetic 60 --out demo_results/     # no data needed

Input: the raw events exported from the Instructor page (CSV), downloaded from the Google Sheet
(File → Download → CSV, or .xlsx), or the local ``events.jsonl``.

Output (in --out):
    participants.csv   one row per participant with every measure (see docs/research/DATA_DICTIONARY.md)
    items.csv          each concept-check question: share correct before and after
    calibration.csv    mean confidence on correct vs. incorrect answers, before and after
    summary.json       paired tests, effect sizes, condition comparison
    report.md          a readable summary of the above
    open_responses.csv written answers (screen for identifying details before quoting)

Keep the output on storage approved by your IRB; do not commit it to GitHub.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qualitylab import research_analysis as RA  # noqa: E402
from qualitylab.learn import concepts as C  # noqa: E402

MISSIONS = ("redbeads", "signals", "funnel", "capability", "pareto", "manager")


def load(path: Path) -> pd.DataFrame:
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return pd.DataFrame(rows)
    if path.suffix in (".xlsx", ".xls"):
        return pd.read_excel(path, sheet_name=0, dtype=str)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _f(x, nd=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    return f"{x:.{nd}f}"


def _p(x):
    if x is None or not np.isfinite(x):
        return "–"
    return "< .001" if x < 0.001 else f"{x:.3f}".lstrip("0")


def report(p: pd.DataFrame, it: pd.DataFrame, cal: pd.DataFrame, s: dict, label: str) -> str:
    L = [f"# Learning Lab results: {label}", ""]
    n = s.get("participants", 0)
    L.append(f"**Participants:** {n}. ")
    if "condition" in p and p["condition"].astype(bool).any():
        L[-1] += "By condition: " + ", ".join(f"{k} {v}" for k, v in p["condition"].value_counts().items()) + "."
    L.append("")
    done = {m: int(p[f"{m}_done"].sum()) for m in MISSIONS if f"{m}_done" in p}
    mins = {m: p[f"{m}_minutes"].median() for m in MISSIONS if f"{m}_minutes" in p}
    L += ["| Mission | Completed | Median minutes |", "|---|---|---|"]
    L += [f"| {m} | {done[m]} | {_f(mins[m], 1)} |" for m in done]
    L.append("")

    c = s.get("concept", {})
    if c.get("n", 0) >= 3:
        L += ["## RQ1 · Concept check (12 items)", "",
              f"Participants with both checks: **{c['n']}**. Mean score rose from **{c['mean_pre']:.0%}** to "
              f"**{c['mean_post']:.0%}** (change {c['mean_diff'] * 100:+.1f} pts, 95 % CI {c['mean_diff_ci95'][0] * 100:+.1f} "
              f"to {c['mean_diff_ci95'][1] * 100:+.1f}). Paired t({c['n'] - 1}) = {_f(c['t'])}, p {_p(c['p'])}; "
              f"Wilcoxon p {_p(c['wilcoxon_p'])}; Cohen's d_z = {_f(c['cohens_dz'])}. "
              f"Class normalised gain ⟨g⟩ = {_f(c.get('class_normalized_gain'))} "
              f"(Hake: < .3 low, .3–.7 medium, > .7 high).", "",
              "| Item | Concept | Pre | Post | Change |", "|---|---|---|---|---|"]
        for iid, r in it.sort_values("change", ascending=False).iterrows():
            L.append(f"| {iid} | {r['concept']} | {_f(r['pre_correct'] * 100, 0)} % | {_f(r['post_correct'] * 100, 0)} % "
                     f"| {_f(r['change'] * 100, 0)} pts |")
        L.append("")
    if "gain_by_condition" in s:
        L += ["## RQ2 · Predict vs. no predict", ""]
        L += [f"* {k}: n = {v['n']}, mean gain {_f(v['mean'] * 100, 1)} pts" for k, v in s["gain_by_condition"].items()]
        w = s.get("gain_condition_welch")
        if w:
            L.append(f"* Welch t-test on gain ({w['comparison']}): difference {_f(w['diff'] * 100, 1)} pts, "
                     f"t = {_f(w['t'])}, p {_p(w['p'])}, d = {_f(w['cohens_d'])}")
        a = s.get("post_condition_ancova", {})
        if "estimate" in a:
            L.append(f"* ANCOVA, post score on pre score and condition ({a['effect']}): "
                     f"{_f(a['estimate'] * 100, 1)} pts, 95 % CI {_f(a['ci95'][0] * 100, 1)} to "
                     f"{_f(a['ci95'][1] * 100, 1)}, p {_p(a['p'])}")
        L.append("")

    L += ["## RQ3 · Decisions inside the missions", ""]
    d = s.get("signals_dprime", {})
    if d.get("n", 0) >= 3:
        L.append(f"* **Signal or Noise:** d′ went from {_f(d['mean_pre'])} in round 1 to {_f(d['mean_post'])} in round 2 "
                 f"(n = {d['n']}, paired t p {_p(d['p'])}, d_z = {_f(d['cohens_dz'])}).")

    def share(col):
        v = p[col].dropna().astype(float) if col in p else pd.Series(dtype=float)
        return f"{v.mean():.0%} of {len(v)}" if len(v) else "–"

    def med(col, fmt="{:.2f}"):
        v = p[col].dropna().astype(float) if col in p else pd.Series(dtype=float)
        return fmt.format(v.median()) if len(v) else "–"

    L += [f"* **Red beads:** attributed the variation to the system: {share('rb_system_cause')}; chose the supplier "
          f"(system) fix: {share('rb_chose_supplier')}; median blame index on Day 1: {med('rb_blame_index')}.",
          f"* **Funnel:** median spread vs. leaving the machine alone: {med('fn_sd_ratio')}× "
          f"(> 1 means adjusting made it worse); median tampering slope {med('fn_tamper_slope')}.",
          f"* **Capability:** found the cheapest way to reach Cpk ≥ 1.33: {share('cap_found_cheapest')}.",
          f"* **Pareto / cost of quality:** median first portfolio {med('pg_first_share_of_optimal', '{:.0%}')} of the "
          f"optimal saving, best {med('pg_best_share_of_optimal', '{:.0%}')}; cost-of-quality classification "
          f"{med('pg_coq_score', '{:.0%}')} correct.",
          f"* **Quality manager:** median extra cost of the first plan over the best one "
          f"{med('mg_first_regret_pct', '{:.0%}')}, of the best plan tried {med('mg_best_regret_pct', '{:.0%}')}.", ""]

    if len(cal):
        L += ["## RQ4 · Confidence calibration", "", "Mean confidence (1–5) on correct and incorrect answers:", "",
              "| Check | Correct | Incorrect |", "|---|---|---|"]
        L += [f"| {k} | {_f(r.get('correct'))} | {_f(r.get('incorrect'))} |" for k, r in cal.iterrows()]
        L.append("")

    if s.get("sus_mean") is not None:
        lk = [f"{k} {_f(p[k].mean())}" for k, _ in C.LEARNING_ITEMS if k in p and p[k].notna().any()]
        L += ["## RQ5 · Experience", "",
              f"System Usability Scale: mean **{_f(s['sus_mean'], 1)}** (n = {int(p['sus'].notna().sum())}; "
              "68 is the usual average). Perceived learning items (1–5): " + ", ".join(lk) + ".", ""]
    L += ["---", "Generated by `scripts/analyze_learning_lab.py`. Definitions: `docs/research/DATA_DICTIONARY.md`."]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("events", nargs="?", type=Path, help="events file (.csv, .xlsx or .jsonl)")
    ap.add_argument("--out", type=Path, default=Path("learning_lab_results"))
    ap.add_argument("--course", help="keep only this course_code (e.g. one section)")
    ap.add_argument("--synthetic", type=int, metavar="N", help="analyse N synthetic participants instead")
    ap.add_argument("--exclude", nargs="*", default=[], metavar="P-CODE", help="withdrawn participants to drop")
    a = ap.parse_args(argv)
    if a.synthetic:
        ev, label = pd.DataFrame(RA.synthetic_events(a.synthetic, seed=1)), f"synthetic demo ({a.synthetic} fake students)"
    elif a.events:
        ev, label = load(a.events), a.events.name
    else:
        ap.error("give an events file or --synthetic N")
    if a.course:
        ev = ev[ev["course_code"] == a.course]
        label += f", course {a.course}"
    if a.exclude:
        ev = ev[~ev["participant_id"].isin(a.exclude)]
    if ev.empty:
        print("No events to analyse.")
        return 1

    p = RA.participants(ev)
    it = RA.items(ev)
    cal = RA.calibration(ev)
    s = RA.summary(p)
    a.out.mkdir(parents=True, exist_ok=True)
    p.to_csv(a.out / "participants.csv")
    it.to_csv(a.out / "items.csv", index_label="item_id")
    cal.to_csv(a.out / "calibration.csv")
    (a.out / "summary.json").write_text(json.dumps(s, indent=2, default=lambda x: None if x != x else x))
    df = RA.to_frame(ev)
    txt = df[df["event_type"] == "text"][["participant_id", "condition", "mission", "item_id", "response"]].copy()
    txt["response"] = txt["response"].map(RA._resp)
    txt.to_csv(a.out / "open_responses.csv", index=False)
    (a.out / "report.md").write_text(report(p, it, cal, s, label), encoding="utf-8")
    print(f"{len(p)} participants, {len(df)} events → {a.out}/")
    print((a.out / "report.md").read_text(encoding="utf-8").split("## RQ4")[0][:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
