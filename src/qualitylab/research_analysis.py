"""Turn Learning Lab event logs into analysis-ready tables.

``participants(events)`` gives one row per participant with every outcome
measure described in ``docs/research/data_dictionary.md``; ``items(events)``
gives pre/post item statistics; ``summary(...)`` runs the headline tests.

``synthetic_events`` creates clearly labeled *fake* data (course code
``SYNTHETIC``) to preview the dashboard and test the analysis pipeline. It
must never be mixed with collected data.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from .learn import concepts as C


def to_frame(events: list[dict] | pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(events).copy() if not isinstance(events, pd.DataFrame) else events.copy()
    if df.empty:
        return df
    for col in ("correct", "confidence", "score", "latency_s"):
        if col in df:
            df[col] = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], errors="coerce", utc=True)
    df = df[df["participant_id"].astype(str).str.len() > 0]
    return df.sort_values("ts_utc").drop_duplicates("event_id")


def _resp(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
        return None
    try:
        return json.loads(v)
    except (TypeError, json.JSONDecodeError):
        return v


def _last(df, **cond):
    m = np.ones(len(df), bool)
    for k, v in cond.items():
        m &= (df[k] == v).to_numpy()
    sub = df[m]
    return sub.iloc[-1] if len(sub) else None


def _first(df, **cond):
    m = np.ones(len(df), bool)
    for k, v in cond.items():
        m &= (df[k] == v).to_numpy()
    sub = df[m]
    return sub.iloc[0] if len(sub) else None


def _attempts(g: pd.DataFrame, mission: str) -> pd.DataFrame:
    """Attempt events of one mission in attempt order (attempt1, attempt2, ...), last session wins."""
    a = g[(g["mission"] == mission) & g["step"].astype(str).str.match(r"attempt\d+$")].copy()
    if a.empty:
        return a
    a["_n"] = a["step"].str[7:].astype(int)
    last_session = a["session_id"].iloc[-1]
    return a[a["session_id"] == last_session].sort_values("_n")


def participants(events) -> pd.DataFrame:
    df = to_frame(events)
    if df.empty:
        return pd.DataFrame()
    rows = []
    for pid, g in df.groupby("participant_id"):
        r: dict = dict(participant_id=pid, condition=g["condition"].mode().iat[0] if g["condition"].notna().any() else "",
                       course_code=g["course_code"].iloc[-1], sessions=g["session_id"].nunique(),
                       first_seen=g["ts_utc"].min(), last_seen=g["ts_utc"].max(), events=len(g))
        for ph in ("pre", "post"):
            # a student who returns in a new session could retake a check: the pre-test is their FIRST
            # attempt (before any mission), the post-test their LAST
            e = _first(g, mission="concept", step=ph, event_type="score") if ph == "pre" else \
                _last(g, mission="concept", step=ph, event_type="score")
            r[f"{ph}_score"] = None if e is None else float(e["score"])
            ans = g[(g["mission"] == "concept") & (g["step"] == ph) & (g["event_type"] == "answer")]
            if e is not None:
                ans = ans[ans["session_id"] == e["session_id"]]
            r[f"{ph}_confidence"] = float(ans["confidence"].mean()) if len(ans) else None
        if r["pre_score"] is not None and r["post_score"] is not None:
            r["gain"] = r["post_score"] - r["pre_score"]
            r["normalized_gain"] = C.normalized_gain(r["pre_score"], r["post_score"])
        for m in ("processlab", "redbeads", "signals", "funnel", "capability", "pareto", "manager"):
            e = _last(g, mission=m, event_type="complete")
            r[f"{m}_done"] = e is not None
            r[f"{m}_minutes"] = None if e is None or pd.isna(e["latency_s"]) else float(e["latency_s"]) / 60
        # mission measures
        e = _last(g, mission="redbeads", item_id="RB_WHY")
        r["rb_system_cause"] = None if e is None else bool(e["correct"])
        e = _last(g, mission="redbeads", step="reveal", event_type="result")
        r["rb_blame_index"] = None if e is None else float(e["score"])
        e = _last(g, mission="redbeads", step="system_change")
        r["rb_chose_supplier"] = None if e is None else bool(e["correct"])
        for ph in ("A", "B"):
            e = _last(g, mission="signals", step=f"phase{ph}", event_type="score")
            resp = _resp(e["response"]) if e is not None else None
            r[f"sig_dprime_{ph}"] = None if e is None else float(e["score"])
            r[f"sig_accuracy_{ph}"] = None if not resp else resp.get("accuracy")
            r[f"sig_false_alarms_{ph}"] = None if not resp else resp.get("false_alarms")
            r[f"sig_hits_{ph}"] = None if not resp else resp.get("hits")
        e = _last(g, mission="funnel", step="play", event_type="result")
        det = _resp(e["detail"]) if e is not None else None
        r["fn_sd_ratio"] = None if e is None else float(e["score"])
        r["fn_tamper_slope"] = None if not det else det.get("slope")
        r["fn_share_adjusted"] = None if not det else det.get("share_adjusted")
        e = _last(g, mission="funnel", item_id="FN_BARISTA")
        r["fn_check_correct"] = None if e is None else bool(e["correct"])
        att = _attempts(g, "capability")
        r["cap_attempts"] = len(att) or None
        r["cap_found_cheapest"] = bool(att["correct"].max()) if len(att) else None
        srt = g[(g["mission"] == "capability") & (g["step"] == "sort")]
        r["cap_sort_score"] = float(srt["correct"].sum()) if len(srt) else None
        e = _last(g, mission="pareto", step="coq", event_type="score")
        r["pg_coq_score"] = None if e is None else float(e["score"])
        att = _attempts(g, "pareto")
        r["pg_best_share_of_optimal"] = float(att["score"].max()) if len(att) else None
        r["pg_first_share_of_optimal"] = float(att["score"].iloc[0]) if len(att) else None
        att = _attempts(g, "manager")
        r["mg_first_regret_pct"] = float(att["score"].iloc[0]) if len(att) else None
        r["mg_best_regret_pct"] = float(att["score"].min()) if len(att) else None
        preds = g[g["event_type"] == "prediction"]
        r["predictions_made"] = len(preds)
        r["prediction_accuracy"] = float(preds["correct"].mean()) if preds["correct"].notna().any() else None
        e = _last(g, mission="survey", step="sus", event_type="score")
        r["sus"] = None if e is None else float(e["score"])
        for k, _ in C.LEARNING_ITEMS:
            e = _last(g, mission="survey", item_id=k)
            r[k] = None if e is None else float(_resp(e["response"]))
        r.update(_processlab_measures(g))
        rows.append(r)
    return pd.DataFrame(rows).set_index("participant_id")


# ---------------------------------------------------------------------------
# Process Lab: one row per experiment
# ---------------------------------------------------------------------------

EXPERIMENT_COLUMNS = [
    "participant_id", "condition", "course_code", "session_id", "exp", "ts_utc", "kind", "goal", "n_changed",
    "changed", "setup_seconds", "chart", "rules", "limits_from", "react", "n", "samples", "baseline", "sigma",
    "target", "lsl", "usl", "off_center", "n_process_changes", "change_kinds", "first_change_kind",
    "first_change_at", "first_change_size_sigma", "first_change_in_baseline", "pred_detect", "pred_delay",
    "pred_false_alarms", "pred_oos_pct", "pred_confidence", "pred_why", "pred_detect_correct",
    "pred_delay_abs_error", "pred_delay_log_error", "pred_false_alarm_abs_error", "pred_oos_abs_error", "detected", "delay",
    "false_alarms", "quiet_samples", "investigations", "oos_share", "cost_total", "true_cpk", "replicated",
    "rep_detect_rate", "rep_delay_median", "rep_false_alarms_per_100", "reflection",
]


def experiments(events) -> pd.DataFrame:
    """Every Process Lab experiment with its full design, the prediction, the outcome and what followed.

    ``changed`` lists the settings that differ from the participant's previous experiment, so
    experimentation strategies (e.g. changing one factor at a time) can be studied directly.
    """
    df = to_frame(events)
    if df.empty:
        return pd.DataFrame(columns=EXPERIMENT_COLUMNS)
    d = df[(df["mission"] == "processlab") & df["step"].astype(str).str.match(r"exp\d+$")]
    rows = []
    for (pid, sess, step), g in d.groupby(["participant_id", "session_id", "step"], sort=False):
        setup = g[g["event_type"] == "decision"]
        if setup.empty:
            continue
        e0 = setup.iloc[-1]
        cfg_ = _resp(e0["response"]) or {}
        det = _resp(e0["detail"]) or {}
        P, Mo, ch = cfg_.get("process", {}), cfg_.get("monitor", {}), cfg_.get("changes", [])
        first = min(ch, key=lambda c: c["at"]) if ch else None
        r = dict(participant_id=pid, condition=e0["condition"], course_code=e0["course_code"], session_id=sess,
                 exp=int(str(step)[3:]), ts_utc=e0["ts_utc"], kind=det.get("kind"), goal=det.get("goal"),
                 n_changed=det.get("n_changed"), changed=";".join(det.get("changed", [])),
                 setup_seconds=e0["latency_s"], chart=Mo.get("chart"), rules=Mo.get("rules"),
                 limits_from=Mo.get("limits_from"), react=Mo.get("react"), n=P.get("n"), samples=P.get("samples"),
                 baseline=P.get("baseline"), sigma=P.get("sigma"), target=P.get("target"), lsl=P.get("lsl"),
                 usl=P.get("usl"), off_center=P.get("mean") is not None, n_process_changes=len(ch),
                 change_kinds=";".join(c["kind"] for c in ch),
                 first_change_kind=None if first is None else first["kind"],
                 first_change_at=None if first is None else first["at"],
                 first_change_size_sigma=(None if first is None or first["kind"] == "spread" or not P.get("sigma")
                                          else first["size"] / P["sigma"]),
                 first_change_in_baseline=None if first is None else first["at"] <= P.get("baseline", 0))
        pe = g[g["event_type"] == "prediction"]
        if len(pe):
            pr, sc = _resp(pe.iloc[-1]["response"]) or {}, _resp(pe.iloc[-1]["detail"]) or {}
            r.update(pred_detect=pr.get("detect"), pred_delay=pr.get("delay"), pred_false_alarms=pr.get("false_alarms"),
                     pred_oos_pct=pr.get("oos_pct"), pred_confidence=pe.iloc[-1]["confidence"],
                     pred_why=(pr.get("why") or None), pred_detect_correct=sc.get("detect_correct"),
                     pred_delay_abs_error=sc.get("delay_abs_error"), pred_delay_log_error=sc.get("delay_log_error"),
                     pred_false_alarm_abs_error=sc.get("false_alarm_abs_error"),
                     pred_oos_abs_error=sc.get("oos_abs_error_pct_points"))
        re_ = g[g["event_type"] == "result"]
        if len(re_):
            res = _resp(re_.iloc[-1]["response"]) or {}
            fc = None
            if res.get("changes"):
                fc = min(res["changes"], key=lambda c: c["at"])
            r.update(detected=None if fc is None else fc["detected"], delay=None if fc is None else fc["delay"],
                     false_alarms=res.get("false_alarms"), quiet_samples=res.get("quiet_samples"),
                     investigations=res.get("investigations"), oos_share=res.get("oos_share"),
                     cost_total=(res.get("costs") or {}).get("total"),
                     true_cpk=(res.get("capability") or {}).get("true_cpk"))
        rp = g[g["event_type"] == "replicate"]
        r["replicated"] = bool(len(rp))
        if len(rp):
            rr = _resp(rp.iloc[-1]["response"]) or {}
            fc = (rr.get("changes") or [None])[0]
            r.update(rep_detect_rate=None if not fc else fc.get("detected"),
                     rep_delay_median=None if not fc else fc.get("delay_median"),
                     rep_false_alarms_per_100=rr.get("false_alarms_per_100"))
        tx = g[g["event_type"] == "text"]
        r["reflection"] = _resp(tx.iloc[-1]["response"]) if len(tx) else None
        rows.append(r)
    out = pd.DataFrame(rows).reindex(columns=EXPERIMENT_COLUMNS)
    return out.sort_values(["participant_id", "ts_utc", "exp"]).reset_index(drop=True)


def _processlab_measures(g: pd.DataFrame) -> dict:
    x = experiments(g)
    r: dict = dict(pl_experiments=len(x) or None)
    if x.empty:
        return r
    new = x[x["kind"] == "new"]
    follow = new[new["n_changed"].notna() & (new["n_changed"] > 0)]
    changed = {c for v in x["changed"].dropna() for c in str(v).split(";") if c}
    half = len(x) // 2

    def mean(col, part):
        v = pd.to_numeric(part[col], errors="coerce").dropna()
        return float(v.mean()) if len(v) else None

    first, second = x.iloc[:max(half, 1)], x.iloc[max(half, 1):]
    r.update(pl_new=len(new), pl_reruns=int((x["kind"] == "rerun").sum()), pl_replications=int(x["replicated"].sum()),
             pl_one_factor_share=float((follow["n_changed"] == 1).mean()) if len(follow) else None,
             pl_factors_explored=len(changed), pl_charts_tried=int(x["chart"].nunique()),
             pl_notes=int(x["reflection"].notna().sum()),
             pl_detect_acc_first_half=mean("pred_detect_correct", first),
             pl_detect_acc_second_half=mean("pred_detect_correct", second),
             # |log(predicted / actual delay)|: 0 = exact, 0.69 = off by a factor of 2 (scale-free)
             pl_delay_err_first_half=mean("pred_delay_log_error", first),
             pl_delay_err_second_half=mean("pred_delay_log_error", second),
             pl_fa_err_first_half=mean("pred_false_alarm_abs_error", first),
             pl_fa_err_second_half=mean("pred_false_alarm_abs_error", second))
    return r


def experiment_learning_curve(x: pd.DataFrame, max_k: int = 12) -> pd.DataFrame:
    """Class means of prediction errors by experiment number (1st, 2nd, ... experiment of each student)."""
    if x.empty:
        return pd.DataFrame()
    x = x.copy()
    x["k"] = x.groupby("participant_id").cumcount() + 1
    x = x[x["k"] <= max_k]
    agg = {c: "mean" for c in ("pred_detect_correct", "pred_delay_log_error", "pred_false_alarm_abs_error",
                               "pred_oos_abs_error") if c in x}
    t = x.groupby("k").agg(agg)
    t["students"] = x.groupby("k")["participant_id"].nunique()
    return t


def items(events) -> pd.DataFrame:
    df = to_frame(events)
    if df.empty:
        return pd.DataFrame()
    a = df[(df["mission"] == "concept") & (df["event_type"] == "answer")]
    a = a.sort_values("ts_utc")
    a = pd.concat([a[a["step"] == "pre"].drop_duplicates(["participant_id", "item_id"], keep="first"),
                   a[a["step"] == "post"].drop_duplicates(["participant_id", "item_id"], keep="last")])
    t = a.pivot_table(index="item_id", columns="step", values="correct", aggfunc="mean")
    n = a.pivot_table(index="item_id", columns="step", values="correct", aggfunc="count")
    out = pd.DataFrame(index=[i.id for i in C.ITEMS])
    out["concept"] = [C.ITEM_BY_ID[i].concept for i in out.index]
    for ph in ("pre", "post"):
        out[f"{ph}_correct"] = t.get(ph)
        out[f"{ph}_n"] = n.get(ph)
    out["change"] = out["post_correct"] - out["pre_correct"]
    return out


def paired_test(pre: pd.Series, post: pd.Series) -> dict:
    m = pre.notna() & post.notna()
    x, y = pre[m].astype(float), post[m].astype(float)
    if len(x) < 3:
        return dict(n=int(len(x)))
    d = y - x
    t = stats.ttest_rel(y, x)
    w = stats.wilcoxon(d) if (d != 0).any() else None
    sd = d.std(ddof=1)
    half = stats.t.ppf(0.975, len(d) - 1) * sd / np.sqrt(len(d))
    return dict(n=int(len(x)), mean_pre=float(x.mean()), mean_post=float(y.mean()), mean_diff=float(d.mean()),
                mean_diff_ci95=[float(d.mean() - half), float(d.mean() + half)],
                t=float(t.statistic), p=float(t.pvalue), cohens_dz=float(d.mean() / sd) if sd > 0 else np.nan,
                wilcoxon_p=float(w.pvalue) if w is not None else np.nan)


def ancova(p: pd.DataFrame, treated: str, control: str) -> dict:
    """Post score on pre score and condition (OLS): the condition effect adjusted for the pre-test."""
    d = p[p["condition"].isin([treated, control])].dropna(subset=["pre_score", "post_score"])
    n = len(d)
    if n < 6 or d["condition"].nunique() < 2:
        return dict(n=int(n))
    X = np.column_stack([np.ones(n), d["pre_score"].to_numpy(float), (d["condition"] == treated).to_numpy(float)])
    y = d["post_score"].to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = n - 3
    cov = (resid @ resid / dof) * np.linalg.pinv(X.T @ X)
    se = float(np.sqrt(cov[2, 2]))
    t = float(beta[2] / se) if se > 0 else np.nan
    half = stats.t.ppf(0.975, dof) * se
    return dict(n=int(n), effect=f"{treated} minus {control}, adjusted for pre-test", estimate=float(beta[2]),
                ci95=[float(beta[2] - half), float(beta[2] + half)], t=t,
                p=float(2 * stats.t.sf(abs(t), dof)) if np.isfinite(t) else np.nan)


def redbeads_debrief(events) -> dict:
    """What students did to the worker with the most red beads on Day 1, and how that worker did on Day 2."""
    df = to_frame(events)
    if df.empty:
        return {}
    d = df[(df["mission"] == "redbeads") & (df["event_type"] == "decision")]
    rows = []
    for _pid, g in d.groupby("participant_id"):
        e1, e2 = g[g["step"] == "day1"], g[g["step"] == "day2"]
        if e1.empty or e2.empty:
            continue
        acts, c1, c2 = _resp(e1["response"].iloc[-1]), _resp(e1["detail"].iloc[-1]), _resp(e2["detail"].iloc[-1])
        if not (isinstance(acts, dict) and isinstance(c1, dict) and isinstance(c2, dict)):
            continue
        c1, c2 = c1.get("counts", {}), c2.get("counts", {})
        if not c1:
            continue
        worst = max(c1, key=c1.get)
        best = min(c1, key=c1.get)
        rows.append(dict(worst_action=acts.get(worst, "No action"), worst_day1=c1[worst], worst_day2=c2.get(worst),
                         best_action=acts.get(best, "No action"), best_day1=c1[best], best_day2=c2.get(best)))
    if not rows:
        return {}
    t = pd.DataFrame(rows)
    return dict(n=len(t), acted_on_worst=float((t["worst_action"] != "No action").mean()),
                worst_actions=t["worst_action"].value_counts().to_dict(),
                worst_day1=float(t["worst_day1"].mean()), worst_day2=float(t["worst_day2"].mean()),
                rewarded_best=float(t["best_action"].eq("Praise + bonus").mean()),
                best_day1=float(t["best_day1"].mean()), best_day2=float(t["best_day2"].mean()))


SIGNAL_CATEGORIES = {"noise_plain": "Ordinary noise", "noise_tempting": "Noise with one point close to a limit",
                     "signal_obvious": "Signal: point beyond a limit", "signal_subtle": "Signal: a pattern (run, trend)"}


def signals_by_category(events) -> pd.DataFrame:
    """Share of charts investigated, by kind of chart and round (the class's false alarms and misses)."""
    df = to_frame(events)
    if df.empty:
        return pd.DataFrame()
    d = df[(df["mission"] == "signals") & (df["event_type"] == "decision")].copy()
    if d.empty:
        return pd.DataFrame()
    d["category"] = d["detail"].map(lambda v: (_resp(v) or {}).get("category") if isinstance(_resp(v), dict) else None)
    d["investigated"] = d["response"].map(lambda v: bool((_resp(v) or {}).get("investigate"))
                                          if isinstance(_resp(v), dict) else np.nan)
    d = d.dropna(subset=["category"])
    t = d.pivot_table(index="category", columns="step", values="investigated", aggfunc="mean")
    t = t.rename(columns={"phaseA": "round 1", "phaseB": "round 2"}).reindex(list(SIGNAL_CATEGORIES))
    t.index = [SIGNAL_CATEGORIES[k] for k in t.index]
    return t


def calibration(events) -> pd.DataFrame:
    """Mean confidence on correct vs. incorrect concept answers, before and after."""
    df = to_frame(events)
    a = df[(df["mission"] == "concept") & (df["event_type"] == "answer")] if not df.empty else df
    if a.empty:
        return pd.DataFrame()
    t = a.assign(answer=np.where(a["correct"] == 1, "correct", "incorrect")).pivot_table(
        index="step", columns="answer", values="confidence", aggfunc="mean")
    return t.reindex([s for s in ("pre", "post") if s in t.index])


def summary(p: pd.DataFrame) -> dict:
    out: dict = dict(participants=int(len(p)))
    if p.empty:
        return out
    if {"pre_score", "post_score"} <= set(p.columns):
        out["concept"] = paired_test(p["pre_score"], p["post_score"])
        both = p.dropna(subset=["pre_score", "post_score"])
        if len(both):
            pre, post = both["pre_score"].mean(), both["post_score"].mean()
            out["concept"]["class_normalized_gain"] = float(C.normalized_gain(pre, post))
            out["concept"]["mean_individual_normalized_gain"] = float(both["normalized_gain"].replace(
                [np.inf, -np.inf], np.nan).mean())
    if {"sig_dprime_A", "sig_dprime_B"} <= set(p.columns):
        out["signals_dprime"] = paired_test(p["sig_dprime_A"], p["sig_dprime_B"])
    if "condition" in p and p["condition"].nunique() > 1 and "gain" in p:
        groups = {c: g["gain"].dropna() for c, g in p.groupby("condition")}
        out["gain_by_condition"] = {c: dict(n=int(len(v)), mean=float(v.mean()) if len(v) else np.nan)
                                    for c, v in groups.items()}
        ok = {c: v for c, v in groups.items() if len(v) >= 2}
        if len(ok) == 2:
            (c1, v1), (c2, v2) = ok.items()
            if "predict" in ok and "no_predict" in ok:
                (c1, v1), (c2, v2) = ("predict", ok["predict"]), ("no_predict", ok["no_predict"])
            t = stats.ttest_ind(v1, v2, equal_var=False)
            sp = np.sqrt(((len(v1) - 1) * v1.var(ddof=1) + (len(v2) - 1) * v2.var(ddof=1)) / (len(v1) + len(v2) - 2))
            out["gain_condition_welch"] = dict(comparison=f"{c1} minus {c2}", diff=float(v1.mean() - v2.mean()),
                                               t=float(t.statistic), p=float(t.pvalue),
                                               cohens_d=float((v1.mean() - v2.mean()) / sp) if sp > 0 else np.nan)
            out["post_condition_ancova"] = ancova(p, c1, c2)
    if "pl_experiments" in p and p["pl_experiments"].notna().any():
        e = p["pl_experiments"].dropna()
        out["processlab"] = dict(students=int(len(e)), experiments_mean=float(e.mean()),
                                 experiments_median=float(e.median()),
                                 one_factor_share_mean=float(p["pl_one_factor_share"].mean())
                                 if p["pl_one_factor_share"].notna().any() else None,
                                 replicated_share=float((p["pl_replications"].fillna(0) > 0)[e.index].mean()))
        if {"pl_delay_err_first_half", "pl_delay_err_second_half"} <= set(p.columns):
            out["processlab"]["delay_error_first_vs_second_half"] = paired_test(
                p["pl_delay_err_first_half"], p["pl_delay_err_second_half"])
        if {"pl_detect_acc_first_half", "pl_detect_acc_second_half"} <= set(p.columns):
            out["processlab"]["detect_accuracy_first_vs_second_half"] = paired_test(
                p["pl_detect_acc_first_half"], p["pl_detect_acc_second_half"])
    if "sus" in p:
        out["sus_mean"] = float(p["sus"].mean()) if p["sus"].notna().any() else None
    return out


# ---------------------------------------------------------------------------
# synthetic data (for previews and tests only)
# ---------------------------------------------------------------------------

def synthetic_events(n: int = 40, seed: int = 0, conditions=("predict", "no_predict")) -> list[dict]:
    """Plausible but entirely fake event logs. Course code is always ``SYNTHETIC``."""
    from .research import assign_condition, make_event

    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        pid = f"P-SYN{i:05d}"
        cond = assign_condition(pid, conditions)
        sess = f"syn{i:05d}"
        ability = rng.normal(0, 1)
        boost = 0.12 if cond == "predict" else 0.08

        def ev(sess=sess, pid=pid, cond=cond, **kw):
            out.append(make_event(session_id=sess, participant_id=pid, condition=cond, course_code="SYNTHETIC", **kw))

        ev(mission="consent", step="consent", event_type="consent", response=dict(agreed=True, adult=True))
        p_pre = 1 / (1 + np.exp(-(ability * 0.8 - 0.2)))
        p_post = min(0.98, p_pre + boost + 0.25 * (1 - p_pre))
        for ph, pp in (("pre", p_pre), ("post", p_post)):
            corr = rng.random(len(C.ITEMS)) < pp
            for it, c in zip(C.ITEMS, corr):
                ev(mission="concept", step=ph, event_type="answer", item_id=it.id,
                   response=it.answer if c else (it.answer + 1) % len(it.options), correct=bool(c),
                   confidence=int(np.clip(round(3 + ability + rng.normal(0, 1)), 1, 5)))
            ev(mission="concept", step=ph, event_type="score", score=float(corr.mean()))
        from .learn import redbeads as RB
        days = [{w: int(rng.binomial(RB.PADDLE, RB.RED_SHARE)) for w in RB.WORKERS} for _ in range(2)]
        worst = max(days[0], key=days[0].get)
        acts = {w: ("Warning" if w == worst and rng.random() < 0.7 else "No action") for w in RB.WORKERS}
        for k in (1, 2):
            ev(mission="redbeads", step=f"day{k}", event_type="decision", response=acts if k == 1 else {},
               detail=dict(counts=days[k - 1]))
        why = rng.random() < 0.35 + 0.1 * ability
        ev(mission="redbeads", step="why", event_type="answer", item_id="RB_WHY", response=1 if why else 0,
           correct=why)
        ev(mission="redbeads", step="reveal", event_type="result", score=float(np.clip(rng.beta(2, 3), 0, 1)))
        ev(mission="redbeads", step="system_change", event_type="decision", response="supplier",
           correct=rng.random() < 0.6)
        ev(mission="redbeads", step="end", event_type="complete", latency_s=float(rng.normal(600, 120)))
        dA = rng.normal(0.9 + 0.3 * ability, 0.6)
        dB = dA + rng.normal(0.7 + (0.2 if cond == "predict" else 0), 0.5)
        for ph, d in (("A", dA), ("B", dB)):
            for cat, base in (("noise_plain", 0.15), ("noise_tempting", 0.55), ("signal_obvious", 0.9),
                              ("signal_subtle", 0.35)):
                inv = rng.random() < (base + (0.25 if ph == "B" and cat == "signal_subtle" else 0)
                                      - (0.2 if ph == "B" and cat == "noise_tempting" else 0))
                ev(mission="signals", step=f"phase{ph}", event_type="decision", item_id=f"{ph}{cat}",
                   response=dict(investigate=bool(inv)), correct=bool(inv) == cat.startswith("signal"),
                   detail=dict(category=cat, is_signal=cat.startswith("signal")))
            ev(mission="signals", step=f"phase{ph}", event_type="score", score=float(d),
               response=dict(accuracy=float(stats.norm.cdf(d / 2)), hits=int(rng.integers(1, 5)),
                             false_alarms=int(rng.integers(0, 3))))
        ev(mission="signals", step="end", event_type="complete", latency_s=float(rng.normal(800, 150)))
        ratio = float(np.exp(rng.normal(0.25, 0.2)))
        ev(mission="funnel", step="play", event_type="result", score=ratio,
           detail=dict(slope=float(-np.clip(rng.normal(0.6, 0.3), 0, 1.2)), share_adjusted=float(rng.uniform(0.3, 1))))
        ev(mission="funnel", step="check", event_type="answer", item_id="FN_BARISTA", correct=rng.random() < 0.75)
        ev(mission="funnel", step="end", event_type="complete", latency_s=float(rng.normal(500, 100)))
        for k in range(int(rng.integers(1, 4))):
            ev(mission="capability", step=f"attempt{k + 1}", event_type="decision", correct=rng.random() < 0.4,
               score=float(rng.uniform(0.6, 1.9)))
        for k in range(8):
            ev(mission="capability", step="sort", event_type="answer", item_id=f"Q{'ABCD'[k // 2]}_{('control', 'capable')[k % 2]}",
               correct=rng.random() < 0.7)
        ev(mission="capability", step="end", event_type="complete", latency_s=float(rng.normal(650, 120)))
        ev(mission="pareto", step="coq", event_type="score", score=float(rng.integers(4, 9) / 8))
        firsts = float(rng.uniform(0.7, 1.0))
        ev(mission="pareto", step="attempt1", event_type="decision", score=firsts)
        ev(mission="pareto", step="attempt2", event_type="decision", score=float(min(1, firsts + rng.uniform(0, 0.2))))
        ev(mission="pareto", step="end", event_type="complete", latency_s=float(rng.normal(650, 120)))
        r1 = float(rng.uniform(0.02, 0.6))
        ev(mission="manager", step="attempt1", event_type="decision", score=r1)
        ev(mission="manager", step="attempt2", event_type="decision", score=float(r1 * rng.uniform(0.2, 0.9)))
        ev(mission="manager", step="end", event_type="complete", latency_s=float(rng.normal(550, 100)))
        if cond != "no_predict":
            for m in ("redbeads", "funnel", "capability", "pareto"):
                ev(mission=m, step="predict", event_type="prediction", correct=rng.random() < 0.35)
        sus = [int(np.clip(round(rng.normal(4 if j % 2 == 0 else 2, 0.8)), 1, 5)) for j in range(10)]
        ev(mission="survey", step="sus", event_type="score", score=C.sus_score(sus), response=sus)
        for k, _ in C.LEARNING_ITEMS:
            if k == "L2" and cond == "no_predict":
                continue
            ev(mission="survey", step="learning", event_type="answer", item_id=k,
               response=int(np.clip(round(rng.normal(4, 0.8)), 1, 5)))
        _synthetic_processlab(ev, rng, ability, cond)
        if rng.random() < 0.3:
            ev(mission="survey", step="open", event_type="text", item_id="most_helpful",
               response=str(rng.choice(["(synthetic) The funnel game surprised me.",
                                        "(synthetic) Red beads: the workers were not the problem.",
                                        "(synthetic) Choosing projects by cost, not count."])))
    return out


def _synthetic_processlab(ev, rng, ability: float, cond: str) -> None:
    """Fake Process Lab sessions: real simulations of plausible, evolving experiment designs."""
    from .learn import process_lab as PL

    exp = PL.Experiment(PL.Process(), [PL.Change("shift", 35, float(rng.choice([0.5, 1.0, 1.5])))], PL.Monitor())
    prev = None
    careful = 1 / (1 + np.exp(-ability))          # more able students vary one factor at a time more often
    n_exp = int(rng.integers(2, 6) + round(3 * careful))
    ev(mission="processlab", step="start", event_type="start")
    for k in range(1, n_exp + 1):
        kind = "new"
        if k > 1 and rng.random() < 0.15:
            kind = "rerun"
        elif k > 1:
            d = exp.to_dict()
            moves = int(1 if rng.random() < 0.35 + 0.5 * careful else rng.integers(2, 4))
            for _ in range(moves):
                f = rng.choice(["n", "chart", "rules", "size", "limits", "react"])
                if f == "n":
                    d["process"]["n"] = int(rng.choice([1, 2, 3, 5, 8]))
                elif f == "chart":
                    d["monitor"]["chart"] = str(rng.choice(["shewhart", "ewma", "cusum"]))
                elif f == "rules":
                    d["monitor"]["rules"] = str(rng.choice(list(PL.RULE_SETS)))
                elif f == "size":
                    d["changes"][0]["size"] = float(rng.choice([0.25, 0.5, 1.0, 1.5, 2.0]))
                elif f == "limits":
                    d["monitor"]["limits_from"] = str(rng.choice(["baseline", "known"]))
                else:
                    d["monitor"]["react"] = bool(rng.random() < 0.8)
            exp = PL.Experiment.from_dict(d)
        d = exp.to_dict()
        changed = PL.diff(prev, d)
        seed = int(rng.integers(1, 2**31 - 1))
        ev(mission="processlab", step=f"exp{k}", event_type="decision", response=d,
           latency_s=float(rng.gamma(4, 15)),
           detail=dict(kind=kind, changed=changed, n_changed=len(changed), goal="explore", seed=seed))
        r = PL.run(exp, seed, keep_data=False)
        o = r["changes"][0]
        if cond != "no_predict":
            skill = 0.55 + 0.35 * (1 - np.exp(-(k - 1) / 3)) * careful   # predictions improve with experience
            det = o["detected"] if rng.random() < skill else not o["detected"]
            delay = max(1, int(round((o["delay"] or 10) * np.exp(rng.normal(0, 1.1 - 0.7 * skill))))) if det else None
            fa = max(0, int(round(r["false_alarms"] + rng.normal(0, 2.5 - 1.5 * skill))))
            pred = dict(detect="Yes" if det else "No", delay=delay, false_alarms=fa,
                        oos_pct=round(max(0.0, 100 * r["oos_share"] * np.exp(rng.normal(0, 1))), 3), why="")
            sc = dict(detect_correct=bool(det == o["detected"]), false_alarm_abs_error=abs(fa - r["false_alarms"]),
                      oos_abs_error_pct_points=abs(pred["oos_pct"] - 100 * r["oos_share"]))
            if det and o["detected"]:
                sc["delay_abs_error"] = abs(delay - o["delay"])
                sc["delay_log_error"] = abs(float(np.log(delay / o["delay"])))
            ev(mission="processlab", step=f"exp{k}", event_type="prediction", response=pred,
               confidence=int(np.clip(round(3 + ability + rng.normal(0, 1)), 1, 5)), correct=sc["detect_correct"],
               score=sc.get("delay_abs_error"), detail=sc)
        ev(mission="processlab", step=f"exp{k}", event_type="result", score=r["costs"]["total"],
           response=dict(changes=r["changes"], false_alarms=r["false_alarms"], quiet_samples=r["quiet_samples"],
                         investigations=r["investigations"], oos_share=r["oos_share"], costs=r["costs"],
                         capability=r["capability"], chart=r["chart_name"]))
        if rng.random() < 0.15 + 0.3 * careful:
            rep = PL.replicate(exp, reps=30, seed=seed)
            ev(mission="processlab", step=f"exp{k}", event_type="replicate", score=rep["cost"],
               response={kk: v for kk, v in rep.items() if kk != "changes"}
               | dict(changes=[{kk: v for kk, v in c.items() if kk != "delays"} for c in rep["changes"]]))
        if rng.random() < 0.2:
            ev(mission="processlab", step=f"exp{k}", event_type="text", item_id="PL_REFLECT",
               response="(synthetic) A bigger sample caught the shift sooner.")
        prev = d
    ev(mission="processlab", step="end", event_type="complete", latency_s=float(rng.normal(1500, 400)))
