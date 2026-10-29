"""SECOM case study: can process-monitoring methods flag failing wafers?

Data: UCI SECOM (McCann & Johnston, 2008), CC BY 4.0. 1,567 wafers from a
semiconductor fab, Jul–Oct 2008, each with 590 in-process sensor readings and a
pass/fail result from final test (104 fails, 6.6 %).

Design (chosen to avoid the leakage common in SECOM notebooks):
* Chronological split: the first 60 % of wafers are the reference ("Phase I")
  window; the last 40 % are the test ("Phase II") window. Nothing about the
  test window is used for preprocessing, model fitting or threshold choice.
* Preprocessing fit on the reference window only: drop features with > 50 %
  missing or ~zero variance, median-impute, standardize.
* Monitoring methods are fit on *passing* reference wafers only (they model
  normal operation, as a control chart does); the supervised baseline uses the
  reference labels.
* Each method gives a wafer an anomaly score. Alarm thresholds are set so that
  5 % of passing reference wafers would alarm (a fixed false-alarm budget),
  then applied unchanged to the test window.

Methods compared
1. Univariate SPC: an individuals chart for every sensor, limits ±3σ from the
   reference window; score = number of sensors beyond their limits.
2. PCA + Hotelling T²: T² on the principal components explaining 90 % of the
   reference variance.
3. PCA + SPE (Q statistic): squared residual outside that PCA model.
4. Isolation Forest (unsupervised machine learning).
5. Supervised baseline: L2-regularized logistic regression trained on the
   reference labels (class-weighted).

Run:
    python case_studies/secom/secom_case_study.py            # downloads data from UCI
    python case_studies/secom/secom_case_study.py --data PATH  # local secom.zip / folder / uci-secom.csv
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.ensemble import IsolationForest  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from qualitylab.plotting import CRITICAL, INK, INK_2, INK_3, SERIES, _style  # noqa: E402

UCI_URL = "https://archive.ics.uci.edu/static/public/179/secom.zip"
SEED = 445
REF_FRAC = 0.60
FALSE_ALARM = 0.05
METHOD_COLORS = {  # categorical slots, fixed order
    "Univariate SPC (count of sensors beyond 3σ)": "#2a78d6",
    "PCA + Hotelling T²": "#eb6834",
    "PCA + SPE (Q)": "#1baf7a",
    "Isolation Forest": "#6250d6",
    "Logistic regression (supervised)": "#52514e",
}


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

def load_secom(path: str | None) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Return (X, y, timestamp) with y = 1 for fail. Accepts the UCI zip/folder or the Kaggle CSV."""
    if path and path.endswith(".csv"):
        df = pd.read_csv(path)
        label = "Pass/Fail" if "Pass/Fail" in df.columns else "Pass_Fail"
        y = (df[label] == 1).astype(int)
        t = repair_swapped_dates(pd.to_datetime(df["Time"]))
        X = df.drop(columns=["Time", label])
        X.columns = [f"s{int(c):03d}" for c in X.columns]
        return X, y, t

    if path and Path(path).is_dir():
        data = Path(path, "secom.data").read_text()
        labels = Path(path, "secom_labels.data").read_text()
    else:
        if path:
            raw = Path(path).read_bytes()
        else:
            print(f"downloading {UCI_URL} …")
            raw = urllib.request.urlopen(UCI_URL, timeout=60).read()
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            data = z.read("secom.data").decode()
            labels = z.read("secom_labels.data").decode()
    X = pd.read_csv(io.StringIO(data), sep=r"\s+", header=None, na_values="NaN")
    X.columns = [f"s{i:03d}" for i in range(X.shape[1])]
    # each line looks like:  -1 "19/07/2008 11:55:00"
    lab = pd.Series(labels.strip().splitlines()).str.extract(r'^\s*(-?1)\s+"?([^"]+?)"?\s*$')
    if lab.isna().any().any():
        raise ValueError("could not parse secom_labels.data")
    y = (lab[0].astype(int) == 1).astype(int)
    t = pd.to_datetime(lab[1], format="%d/%m/%Y %H:%M:%S")
    return X, y, t


def repair_swapped_dates(t: pd.Series) -> pd.Series:
    """Fix day/month swaps found in some redistributed copies of SECOM.

    The UCI file stores dates as dd/mm/yyyy, and rows are in production order
    (19 Jul – 17 Oct 2008). Copies converted with a month-first parser turn
    e.g. 5 Aug into "2008-05-08". For each row we keep the reading (as parsed,
    or with day and month swapped) that is consistent with the row order.
    """
    lo, hi = pd.Timestamp("2008-07-19"), pd.Timestamp("2008-10-18")
    out, prev, fixed = [], lo, 0
    for ts in t:
        cands = [ts]
        if ts.day <= 12:
            cands.append(ts.replace(month=ts.day, day=ts.month))
        ok = [c for c in cands if lo <= c < hi and c >= prev]
        pick = min(ok) if ok else ts
        fixed += pick is not ts and pick != ts
        out.append(pick)
        prev = pick
    res = pd.Series(out, index=t.index)
    if fixed:
        print(f"note: repaired {fixed} timestamps with day/month swapped")
    if not res.is_monotonic_increasing:
        raise ValueError("timestamps are not in production order after repair")
    return res


# ---------------------------------------------------------------------------
# methods
# ---------------------------------------------------------------------------

class Preprocessor:
    def fit(self, X: pd.DataFrame):
        miss = X.isna().mean()
        keep = miss[miss <= 0.5].index
        med = X[keep].median()
        Xi = X[keep].fillna(med)
        sd = Xi.std(ddof=1)
        keep = sd[sd > 1e-8].index
        self.cols, self.med, self.mu, self.sd = keep, med[keep], Xi[keep].mean(), sd[keep]
        self.dropped_missing = int((miss > 0.5).sum())
        self.dropped_constant = int(len(sd) - len(keep))
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        return ((X[self.cols].fillna(self.med) - self.mu) / self.sd).to_numpy()


def univariate_spc_score(Zref_pass: np.ndarray, Z: np.ndarray) -> np.ndarray:
    """Number of sensors outside ±3σ individuals-chart limits.

    σ per sensor = average moving range / 1.128 over the reference passing
    wafers, in time order (the standard I-chart estimate).
    """
    mu = Zref_pass.mean(axis=0)
    sig = np.abs(np.diff(Zref_pass, axis=0)).mean(axis=0) / 1.128
    sig[sig < 1e-8] = np.inf
    return (np.abs(Z - mu) > 3 * sig).sum(axis=1).astype(float)


def pca_scores(Zref_pass: np.ndarray, Z: np.ndarray, var: float = 0.90):
    pca = PCA(n_components=var, svd_solver="full", random_state=SEED).fit(Zref_pass)
    T = pca.transform(Z)
    t2 = (T**2 / pca.explained_variance_).sum(axis=1)
    spe = ((Z - pca.inverse_transform(T)) ** 2).sum(axis=1)
    return t2, spe, pca.n_components_


def threshold_at(scores_ref_pass: np.ndarray, fa: float = FALSE_ALARM) -> float:
    return float(np.quantile(scores_ref_pass, 1 - fa))


def bootstrap_ci(y, s, fn, B=2000, seed=SEED):
    rng = np.random.default_rng(seed)
    n = len(y)
    vals = []
    for _ in range(B):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        vals.append(fn(y[i], s[i]))
    return np.percentile(vals, [2.5, 97.5])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def score_all(X: pd.DataFrame, y: pd.Series, n_ref: int, ci: bool = True):
    """Fit every method on the first n_ref wafers; return (metrics table, scores, extras)."""
    ref, test = slice(0, n_ref), slice(n_ref, None)
    y_ref, y_test = y[ref].to_numpy(), y[test].to_numpy()

    pre = Preprocessor().fit(X.iloc[ref])
    Z = pre.transform(X)
    Zref = Z[ref]
    Zref_pass = Zref[y_ref == 0]

    scores: dict[str, np.ndarray] = {}
    scores["Univariate SPC (count of sensors beyond 3σ)"] = univariate_spc_score(Zref_pass, Z)
    t2, spe, k = pca_scores(Zref_pass, Z)
    scores["PCA + Hotelling T²"] = t2
    scores["PCA + SPE (Q)"] = spe
    iso = IsolationForest(n_estimators=500, random_state=SEED).fit(Zref_pass)
    scores["Isolation Forest"] = -iso.score_samples(Z)
    lr = LogisticRegression(C=0.01, class_weight="balanced", max_iter=5000).fit(Zref, y_ref)
    scores["Logistic regression (supervised)"] = lr.decision_function(Z)

    rows = []
    ref_pass_mask = np.zeros(len(X), bool)
    ref_pass_mask[:n_ref] = y_ref == 0
    for name, sc in scores.items():
        st = sc[test]
        thr = threshold_at(sc[ref_pass_mask])
        alarm = st > thr
        tp = int((alarm & (y_test == 1)).sum())
        fp = int((alarm & (y_test == 0)).sum())
        row = {"method": name, "ROC AUC": roc_auc_score(y_test, st)}
        if ci:
            row["ROC AUC 95% CI"] = "{:.2f}–{:.2f}".format(*bootstrap_ci(y_test, st, roc_auc_score))
        row.update({
            "average precision": average_precision_score(y_test, st),
            "fails caught (recall)": tp / max(1, y_test.sum()),
            "false-alarm rate on passing wafers": fp / max(1, (y_test == 0).sum()),
            "precision of alarms": tp / max(1, tp + fp),
            "alarms": int(alarm.sum()),
        })
        rows.append(row)
    extras = dict(pre=pre, pca_components=int(k), ref_pass_mask=ref_pass_mask)
    return pd.DataFrame(rows).set_index("method"), scores, extras


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", help="secom.zip, a folder with secom.data + secom_labels.data, or uci-secom.csv")
    ap.add_argument("--out", default=str(HERE / "results"))
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    X, y, t = load_secom(args.data)
    if not t.is_monotonic_increasing:
        raise ValueError("expected wafers in production order")
    assert X.shape == (1567, 590), X.shape
    n_ref = int(round(REF_FRAC * len(X)))
    test = slice(n_ref, None)
    y_ref, y_test = y[:n_ref].to_numpy(), y[test].to_numpy()

    res, scores, ex = score_all(X, y, n_ref)
    pre, k, ref_pass_mask = ex["pre"], ex["pca_components"], ex["ref_pass_mask"]
    res.to_csv(out / "metrics.csv")

    # robustness: does the conclusion depend on where we split?
    rob = {}
    for frac in (0.5, 0.6, 0.7):
        r, _, _ = score_all(X, y, int(round(frac * len(X))), ci=False)
        rob[f"reference = first {frac:.0%}"] = r["ROC AUC"]
    rob = pd.DataFrame(rob)
    rob.to_csv(out / "robustness_auc.csv")

    meta = dict(
        wafers=len(X), sensors=X.shape[1], fails=int(y.sum()), fail_rate=float(y.mean()),
        reference_wafers=n_ref, reference_fails=int(y_ref.sum()),
        test_wafers=len(X) - n_ref, test_fails=int(y_test.sum()),
        reference_period=f"{t.iloc[0]:%Y-%m-%d} to {t.iloc[n_ref - 1]:%Y-%m-%d}",
        test_period=f"{t.iloc[n_ref]:%Y-%m-%d} to {t.iloc[-1]:%Y-%m-%d}",
        sensors_used=len(pre.cols), dropped_missing=pre.dropped_missing, dropped_constant=pre.dropped_constant,
        pca_components=int(k), false_alarm_budget=FALSE_ALARM,
    )
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    # ---------------- figures ----------------
    # 1) ROC curves
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    _style(ax)
    ax.grid(axis="x", color="#e8e7e3", lw=0.8)
    for name, s in scores.items():
        fpr, tpr, _ = roc_curve(y_test, s[test])
        ax.plot(fpr, tpr, lw=2, color=METHOD_COLORS[name],
                ls="--" if "supervised" in name else "-",
                label=f"{name}  (AUC {res.loc[name, 'ROC AUC']:.2f})")
    ax.plot([0, 1], [0, 1], color=INK_3, lw=1, ls=":")
    ax.axvline(FALSE_ALARM, color=INK_3, lw=1)
    ax.text(FALSE_ALARM + 0.01, 0.98, "5 % false-alarm\nbudget", fontsize=8, color=INK_2, va="top")
    ax.set_xlabel("false-alarm rate (passing wafers flagged)", color=INK_2)
    ax.set_ylabel("share of failing wafers flagged", color=INK_2)
    ax.set_title("SECOM test window: who catches failing wafers?", loc="left", fontsize=11,
                 fontweight="bold", color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.13), labelcolor=INK_2)
    fig.savefig(out / "roc.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 2) T² chart over time with fails marked
    best = res["ROC AUC"].drop("Logistic regression (supervised)").idxmax()
    s = scores[best]
    thr = threshold_at(s[ref_pass_mask])
    fig, ax = plt.subplots(figsize=(11, 3.8))
    _style(ax)
    x = np.arange(1, len(s) + 1)
    ax.plot(x, s, color=SERIES, lw=0.8, alpha=0.8)
    fails = np.flatnonzero(y.to_numpy() == 1)
    ax.scatter(x[fails], s[fails], s=34, marker="^", color=CRITICAL, zorder=3, label="wafer failed final test")
    ax.axhline(thr, color=INK, lw=1.2, ls=(0, (5, 3)))
    ax.text(len(s) + 5, thr, " alarm limit\n (5 % FA)", va="center", fontsize=8, color=INK_2)
    ax.axvline(n_ref + 0.5, color=INK_3, lw=1, ls=":")
    top = np.quantile(s, 0.995) * 1.15
    ax.set_ylim(0, top)
    ax.text(n_ref - 5, top, "reference (Phase I)  ", ha="right", va="top", fontsize=8, color=INK_2)
    ax.text(n_ref + 5, top, "  test (Phase II)", ha="left", va="top", fontsize=8, color=INK_2)
    ax.set_xlabel("wafer, in production order", color=INK_2)
    ax.set_ylabel(best.split(" (")[0], color=INK_2)
    ax.set_title(f"Monitoring chart: {best}", loc="left", fontsize=11, fontweight="bold", color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.14), labelcolor=INK_2)
    fig.savefig(out / "monitoring_chart.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 3) fail rate over time (is the process itself stable?)
    wk = pd.DataFrame({"t": t, "y": y}).set_index("t").resample("W")["y"].agg(["sum", "count"])
    wk = wk[wk["count"] > 0]
    fig, ax = plt.subplots(figsize=(9, 3.2))
    _style(ax)
    rate = wk["sum"] / wk["count"]
    pbar = y.mean()
    ucl = pbar + 3 * np.sqrt(pbar * (1 - pbar) / wk["count"])
    ax.plot(rate.index, rate, color=SERIES, lw=2, marker="o", ms=4.5)
    ax.step(rate.index, ucl, where="mid", color=INK, lw=1.2, ls=(0, (5, 3)))
    ax.axhline(pbar, color=INK_2, lw=1.2)
    ax.set_ylabel("fail rate", color=INK_2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Weekly fail rate (p chart, all wafers)", loc="left", fontsize=11, fontweight="bold", color=INK)
    fig.savefig(out / "weekly_fail_rate.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 4) drift: share of passing wafers beyond the SPE limit, week by week
    spe = scores["PCA + SPE (Q)"]
    thr = threshold_at(spe[ref_pass_mask])
    passing = y.to_numpy() == 0
    wk2 = pd.DataFrame({"t": t[passing], "beyond": spe[passing] > thr}).set_index("t").resample("W")["beyond"].mean()
    fig, ax = plt.subplots(figsize=(9, 3.2))
    _style(ax)
    ax.plot(wk2.index, wk2.values, color="#1baf7a", lw=2, marker="o", ms=4.5)
    ax.axhline(FALSE_ALARM, color=INK_2, lw=1.2, ls=(0, (5, 3)))
    ax.text(wk2.index[0], FALSE_ALARM + 0.02, "expected if nothing changed (5 %)", fontsize=8, color=INK_2)
    ax.axvline(t.iloc[n_ref], color=INK_3, lw=1, ls=":")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("passing wafers beyond limit", color=INK_2)
    ax.set_title("The process drifted: SPE alarms on *passing* wafers, by week", loc="left", fontsize=11,
                 fontweight="bold", color=INK)
    fig.savefig(out / "spe_drift.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    meta["passing_test_wafers_beyond_spe_limit"] = float((spe[test][y_test == 0] > thr).mean())
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.precision", 3):
        print(json.dumps(meta, indent=2))
        print(res)
        print(rob.round(3))
    print(f"\nwrote results to {out}")


if __name__ == "__main__":
    main()
