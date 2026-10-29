"""SPC Toolkit page: control charts, capability, Pareto, T² and the ARL simulator."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

# make the package importable without installation (e.g. on Streamlit Community Cloud)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import qualitylab as ql  # noqa: E402
from qualitylab import arl, datasets  # noqa: E402
from qualitylab.interpret import explain  # noqa: E402
from qualitylab.plotting import plot_capability, plot_chart, plot_pair, plot_pareto  # noqa: E402
from qualitylab.rules import RULE_DESCRIPTIONS  # noqa: E402

CHARTS = {
    "X̄-R (subgroups, n ≤ 10)": "xbar_r",
    "X̄-S (subgroups, any n)": "xbar_s",
    "I-MR (one value per period)": "imr",
    "p (proportion defective)": "p",
    "np (number defective, constant n)": "np",
    "c (defects per unit, constant unit)": "c",
    "u (defects per unit, varying units)": "u",
    "EWMA (small shifts)": "ewma",
    "CUSUM (small shifts)": "cusum",
}
SUGGESTED = {
    "coffee_fill": "xbar_r", "call_wait": "imr", "invoice_errors": "p", "online_orders": "p",
    "pcb_defects": "c", "hotel_complaints": "u", "shaft_diameter": "xbar_r", "bottling_line": "imr",
    "complaint_reasons": None,
}
RULE_SETS = {
    "Nelson / Minitab (all 8 tests)": "nelson",
    "Western Electric (1, 2, 5, 6)": "western_electric",
    "Limits only (rule 1)": "limits",
    "Attribute default (1–4)": "attribute",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def fig_download(fig, name: str, key: str):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    st.download_button("Download chart (PNG)", buf.getvalue(), file_name=f"{name}.png", mime="image/png", key=key)


def excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31])
    return buf.getvalue()


def numeric_cols(df):
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


@st.cache_data(show_spinner=False)
def read_upload(data: bytes, name: str) -> pd.DataFrame:
    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data))
    return pd.read_csv(io.BytesIO(data))


@st.cache_data(show_spinner="Simulating thousands of runs…")
def cached_arl(shift, lam, L, k, h, reps):
    return {
        "Shewhart (rule 1)": arl.shewhart_arl(shift),
        f"EWMA λ={lam}, L={L}": float(arl.run_lengths("ewma", shift, reps=reps, lam=lam, L=L, seed=1).mean()),
        f"CUSUM k={k}, h={h}": float(arl.run_lengths("cusum", shift, reps=reps, k=k, h=h, seed=1).mean()),
    }


# ---------------------------------------------------------------------------
# sidebar: data
# ---------------------------------------------------------------------------

st.sidebar.caption("SPC Toolkit: control charts, capability and Pareto on practice or uploaded data.")
source = st.sidebar.radio("Data", ["Practice scenario", "Upload my own file"], horizontal=False)

scenario = None
if source == "Practice scenario":
    names = datasets.available()
    titles = {n: datasets.info(n).title for n in names}
    scenario = st.sidebar.selectbox("Scenario", names, format_func=lambda n: titles[n])
    code = st.sidebar.text_input(
        "Personal dataset code (optional)",
        help="Your instructor may ask you to type your student ID or a code here. "
             "Everyone then gets a different version of the same scenario.",
    )
    df = datasets.load(scenario, seed=code or None)
    sc = datasets.info(scenario)
    st.sidebar.info(f"**{sc.title}**\n\n{sc.story}\n\n*Suggested tool:* {sc.chart}")
    st.sidebar.download_button("Download this dataset (CSV)", df.to_csv().encode(),
                               file_name=f"{scenario}{'_' + code if code else ''}.csv", mime="text/csv")
else:
    up = st.sidebar.file_uploader("CSV or Excel file", type=["csv", "xlsx"])
    st.sidebar.caption("Your file is processed in this browser session only and is not stored.")
    if up is None:
        st.title("SPC Toolkit")
        st.write("Upload a CSV or Excel file in the sidebar, or switch to a practice scenario.")
        st.markdown(
            "**Accepted layouts**\n"
            "- *Subgroup data*: one row per subgroup, one column per measurement (e.g. `x1 … x5`), "
            "or one row per measurement with a subgroup-ID column.\n"
            "- *Individual values*: one numeric column.\n"
            "- *Attribute data*: a count column (defectives or defects) and, if it varies, a sample-size column.\n"
            "- *Pareto*: a column of category labels (one row per defect) or categories with counts."
        )
        st.stop()
    df = read_upload(up.getvalue(), up.name)

# widget keys are tied to the dataset so selections reset when the data change
DKEY = f"{scenario}" if scenario else f"upload_{up.name}"

with st.expander(f"View data ({len(df)} rows × {df.shape[1]} columns)", expanded=False):
    st.dataframe(df, width="stretch")

tab_cc, tab_cap, tab_par, tab_t2, tab_arl, tab_help = st.tabs(
    ["Control chart", "Capability", "Pareto", "Multivariate T²", "Which chart is fastest?", "How to read the charts"]
)

# ---------------------------------------------------------------------------
# control charts
# ---------------------------------------------------------------------------

def control_chart_tab():
    nums = numeric_cols(df)
    if not nums:
        st.info("These data have no numeric columns to chart. Try the **Pareto** tab.")
        return
    default = SUGGESTED.get(scenario) if scenario else None
    keys = list(CHARTS.values())
    c1, c2, c3 = st.columns([2, 2, 2])
    chart_label = c1.selectbox("Chart type", list(CHARTS),
                               index=keys.index(default) if default in keys else 0)
    kind = CHARTS[chart_label]
    rules_label = c2.selectbox("Run rules", list(RULE_SETS),
                               index=3 if kind in ("p", "np", "c", "u") else 0,
                               disabled=kind in ("ewma", "cusum"))
    rules = RULE_SETS[rules_label]

    # --- column mapping
    args: dict = {}
    if kind in ("xbar_r", "xbar_s"):
        layout = c3.radio("Layout", ["Wide (one row per subgroup)", "Long (subgroup ID column)"], horizontal=False)
        if layout.startswith("Wide"):
            guess = [c for c in nums if df[c].notna().all()] if scenario else nums
            if scenario == "coffee_fill":
                guess = [c for c in nums if c.startswith("bottle")]
            if scenario == "shaft_diameter":
                guess = [c for c in nums if c.startswith("part")]
            cols = st.multiselect("Measurement columns (one per observation in the subgroup)", nums, default=guess)
            data = df[cols]
        else:
            val = st.selectbox("Measurement column", nums)
            grp = st.selectbox("Subgroup ID column", [c for c in df.columns if c != val])
            data = ql.subgroups_from_long(df, val, grp)
        if data.shape[1] < 2:
            st.warning("Select at least two measurement columns.")
            return
        m_points = len(data)
    elif kind in ("imr", "ewma", "cusum"):
        col = c3.selectbox("Value column", nums)
        data = df[col]
        m_points = len(data)
    elif kind in ("p", "u") and len(nums) < 2:
        st.warning("This chart needs two numeric columns: a count and a sample size (or units). "
                   "These data have only one.")
        return
    elif kind in ("p", "np"):
        dcol = c3.selectbox("Defectives (count) column", nums, index=min(len(nums) - 1, 1))
        if kind == "p":
            ncol = st.selectbox("Sample size column", [c for c in nums if c != dcol])
            args["sizes"] = df[ncol].to_numpy()
        else:
            args["n"] = st.number_input("Constant sample size n", min_value=1, value=50)
        data = df[dcol]
        m_points = len(data)
    elif kind == "c":
        data = df[c3.selectbox("Defect count column", nums, index=len(nums) - 1)]
        m_points = len(data)
    else:  # u
        dcol = c3.selectbox("Defect count column", nums, index=len(nums) - 1)
        ucol = st.selectbox("Units / area of opportunity column", [c for c in nums if c != dcol])
        data = df[dcol]
        args["units"] = df[ucol].to_numpy()
        m_points = len(data)

    # --- options
    with st.expander("Options", expanded=True):
        o1, o2, o3 = st.columns(3)
        use_phase2 = o1.checkbox("Phase I / Phase II", value=scenario in ("coffee_fill", "call_wait", "hotel_complaints"),
                                 help="Estimate the limits from the first part of the data only, then use those "
                                      "fixed limits to monitor the rest.")
        default_p1 = {"coffee_fill": 15, "call_wait": 30, "hotel_complaints": 12}.get(scenario, max(2, m_points // 2))
        phase1 = o1.number_input("Points in Phase I", 2, m_points, min(default_p1, m_points)) if use_phase2 else None
        label_opts = list(range(1, m_points + 1))
        excl = o2.multiselect("Exclude points from the limits (by position)", label_opts,
                              help="Points with a known, removed special cause. They stay on the chart.")
        excl = [e - 1 for e in excl]
        revise = o2.checkbox("Revise limits automatically",
                             help="Repeatedly drop Phase I points beyond the limits and recompute. "
                                  "Justified only when you have found the causes of those points.")
        if kind in ("p", "u"):
            args["laney"] = o3.checkbox("Laney adjustment (very large samples)",
                                        value=scenario == "online_orders")
        if kind == "ewma":
            args["lam"] = o3.slider("λ (weight on newest point)", 0.05, 1.0, 0.2, 0.05)
            args["L"] = o3.number_input("L (limit width)", 1.0, 4.0, 3.0, 0.05)
        if kind == "cusum":
            args["k"] = o3.number_input("k (half the shift to detect, in σ)", 0.1, 2.0, 0.5, 0.1)
            args["h"] = o3.number_input("h (decision interval, in σ)", 1.0, 10.0, 5.0, 0.5)
        labels_col = o3.selectbox("Point labels", ["position"] + [c for c in df.columns if c not in nums or c == df.index.name])

    labels = None if labels_col == "position" else df[labels_col].astype(str).tolist()
    if kind in ("xbar_r", "xbar_s") and labels is not None and len(labels) != len(data):
        labels = None

    common = dict(phase1=phase1, exclude=excl, labels=labels)
    try:
        partner = None
        if kind == "xbar_r":
            res, partner = ql.xbar_r(data, revise=revise, rules=rules, **common)
        elif kind == "xbar_s":
            res, partner = ql.xbar_s(data, revise=revise, rules=rules, **common)
        elif kind == "imr":
            res, partner = ql.imr(data, revise=revise, rules=rules, **common)
        elif kind == "p":
            res = ql.p_chart(data, revise=revise, rules=rules, **args, **common)
        elif kind == "np":
            res = ql.np_chart(data, revise=revise, rules=rules, **args, **common)
        elif kind == "c":
            res = ql.c_chart(data, revise=revise, rules=rules, **common)
        elif kind == "u":
            res = ql.u_chart(data, revise=revise, rules=rules, **args, **common)
        elif kind == "ewma":
            res = ql.ewma(data, **args, **common)
        else:
            res = ql.cusum(data, **args, **common)
    except (ValueError, IndexError, KeyError, TypeError) as e:
        st.error(f"Could not build this chart: {e}")
        return

    title = f"{datasets.info(scenario).title}: {res.name} chart" if scenario else f"{res.name} chart"
    if partner is not None:
        fig = plot_pair(res, partner, title=title.replace(f"{res.name} chart", f"{res.name}-{partner.name} chart"))
    else:
        fig, ax = plt.subplots(figsize=(10, 3.8))
        plot_chart(res, ax, title=title)
    st.pyplot(fig, width="stretch")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("What the chart says")
        for para in explain(res, partner):
            st.markdown("- " + para)
    with right:
        st.subheader("Limits")
        p = res.params
        rows = {"Center line": res.center[-1], "UCL": res.ucl[-1], "LCL": res.lcl[-1]}
        if "sigma" in p:
            rows["Estimated σ (process)"] = float(p["sigma"])
        st.table(pd.Series(rows, name="value").map(lambda v: f"{v:.5g}"))
        if np.unique(np.round(res.ucl, 10)).size > 1:
            st.caption("Limits vary with sample size; the values shown are for the last point.")
        fig_download(fig, f"{res.name}_chart", "dl_cc_png")
        sheets = {res.name: res.to_frame()}
        if partner is not None:
            sheets[partner.name] = partner.to_frame()
        st.download_button("Download results (Excel)", excel_bytes(sheets), file_name=f"{res.name}_chart.xlsx",
                           key="dl_cc_xlsx")
    with st.expander("Point-by-point table"):
        st.dataframe(res.to_frame(), width="stretch")
    plt.close(fig)

with tab_cc:
    control_chart_tab()

# ---------------------------------------------------------------------------
# capability
# ---------------------------------------------------------------------------

with tab_cap:
    nums = numeric_cols(df)
    st.write("Capability compares the voice of the process (its natural spread) with the voice of the "
             "customer (the specification limits). **Check the control chart first**: capability numbers "
             "for an unstable process predict nothing.")
    specs = datasets.info(scenario).specs if scenario else None
    specs = specs or {}
    guess = [c for c in nums if c.startswith(("bottle", "part"))] or nums[:1]
    cols = st.multiselect("Measurement column(s): pick several for subgroup data", nums, default=guess, key=f"capcols_{DKEY}")
    s1, s2, s3 = st.columns(3)
    lsl_on = s1.checkbox("Lower spec (LSL)", value="lsl" in specs)
    lsl = s1.number_input("LSL", value=float(specs.get("lsl", 0.0)), format="%.4f", disabled=not lsl_on)
    usl_on = s2.checkbox("Upper spec (USL)", value="usl" in specs)
    usl = s2.number_input("USL", value=float(specs.get("usl", 1.0)), format="%.4f", disabled=not usl_on)
    tgt_on = s3.checkbox("Target", value="target" in specs)
    tgt = s3.number_input("Target", value=float(specs.get("target", 0.5)), format="%.4f", disabled=not tgt_on)
    if not cols:
        st.info("Choose at least one measurement column.")
    elif not (lsl_on or usl_on):
        st.info("Enter at least one specification limit.")
    else:
        try:
            data = df[cols] if len(cols) > 1 else df[cols[0]]
            cap = ql.capability(data, lsl if lsl_on else None, usl if usl_on else None,
                                target=tgt if tgt_on else None)
        except ValueError as e:
            st.error(str(e))
        else:
            # stability check
            stab = (ql.xbar_s(df[cols])[0] if len(cols) > 1 else ql.imr(df[cols[0]])[0])
            if not stab.in_control:
                st.warning(f"The {stab.name} chart for these data shows {stab.out_of_control.size} signal(s). "
                           "The process may not be stable, so treat these indices with caution.")
            fig, ax = plt.subplots(figsize=(10, 4))
            plot_capability(cap, ax)
            st.pyplot(fig, width="stretch")
            a, b = st.columns(2)
            with a:
                st.subheader("Indices (95 % CI)")
                t = cap.to_frame()
                st.dataframe(t.style.format("{:.3f}", na_rep="–"), width="stretch")
                st.caption(f"Within σ = {cap.sigma_within:.5g} ({cap.sigma_method}); overall σ = "
                           f"{cap.sigma_overall:.5g}; mean = {cap.mean:.5g}; n = {cap.n}.")
            with b:
                st.subheader("Parts per million outside spec")
                st.dataframe(cap.ppm.style.format("{:,.0f}"), width="stretch")
                st.caption(f"Normality: {cap.normality['test']} p = {cap.normality['p_value']:.3f}")
            st.subheader("Interpretation")
            for line in cap.interpretation().splitlines():
                st.markdown("- " + line)
            fig_download(fig, "capability", "dl_cap")
            plt.close(fig)

# ---------------------------------------------------------------------------
# pareto
# ---------------------------------------------------------------------------

with tab_par:
    cats = [c for c in df.columns
            if (pd.api.types.is_object_dtype(df[c]) or isinstance(df[c].dtype, pd.CategoricalDtype)
                or pd.api.types.is_string_dtype(df[c]))
            and 1 < df[c].nunique() <= min(50, max(2, len(df) // 2))]
    if not cats:
        st.info("No category column found in these data. Try the *Customer complaint reasons* scenario.")
    else:
        default_cat = "complaint_reason" if "complaint_reason" in cats else cats[0]
        cat = st.selectbox("Category column", cats, index=cats.index(default_cat))
        cnt = st.selectbox("Count column (leave as 'one row per item' if each row is one defect)",
                           ["one row per item"] + numeric_cols(df))
        other = st.slider("Fold categories smaller than this share into 'Other'", 0.0, 0.10, 0.0, 0.01)
        tbl = ql.pareto(df, category=cat, count=None if cnt == "one row per item" else cnt,
                        other_below=other or None)
        fig, ax = plt.subplots(figsize=(10, 4.2))
        plot_pareto(tbl, ax)
        st.pyplot(fig, width="stretch")
        vf = tbl.index[tbl.vital_few].tolist()
        st.markdown(f"**{len(vf)} of {len(tbl)} categories** account for "
                    f"{tbl.loc[vf, 'share'].sum():.0%} of all items: {', '.join(map(str, vf))}. "
                    "Start improvement work there.")
        st.dataframe(tbl.style.format({"share": "{:.1%}", "cumulative_share": "{:.1%}"}), width="stretch")
        fig_download(fig, "pareto", "dl_par")
        plt.close(fig)

# ---------------------------------------------------------------------------
# T²
# ---------------------------------------------------------------------------

with tab_t2:
    st.write("When several quality characteristics are related, checking each on its own chart can miss "
             "an unusual *combination*. Hotelling's T² chart watches them jointly.")
    nums = numeric_cols(df)
    sel = st.multiselect("Variables (2 or more)", nums, default=nums if scenario == "bottling_line" else nums[:3],
                         key=f"t2cols_{DKEY}")
    if len(sel) >= 2:
        X = df[sel].dropna()
        try:
            t2 = ql.hotelling_t2(X)
        except ValueError as e:
            st.error(str(e))
        else:
            fig, ax = plt.subplots(figsize=(10, 3.8))
            plot_chart(t2, ax, title="Hotelling T² chart")
            st.pyplot(fig, width="stretch")
            if t2.in_control:
                st.success("No unusual combinations found.")
            else:
                st.markdown(f"Signals at point(s) **{', '.join(map(str, t2.labels[t2.out_of_control]))}**.")
                single = {}
                for c in sel:
                    i, _ = ql.imr(X[c], rules="limits")
                    single[c] = ", ".join(map(str, i.labels[i.out_of_control])) or "none"
                st.write("Signals on each variable's own individuals chart:")
                st.table(pd.Series(single, name="points beyond limits"))
                st.write("Share of each variable in the flagged points' deviations (ignores correlation):")
                st.dataframe(t2.extra["contributions"].iloc[t2.out_of_control].style.format("{:.0%}"))
            plt.close(fig)
    else:
        st.info("Pick at least two numeric columns.")

# ---------------------------------------------------------------------------
# ARL simulator
# ---------------------------------------------------------------------------

with tab_arl:
    st.write("Suppose the process mean suddenly shifts. **How many points, on average, until each chart "
             "notices?** That is the *average run length* (ARL). With no shift, the ARL is the average time "
             "between false alarms, so we want it large; after a shift we want it small.")
    a1, a2, a3 = st.columns(3)
    shift = a1.slider("Size of the shift (in σ)", 0.0, 3.0, 1.0, 0.25)
    lam = a2.slider("EWMA λ", 0.05, 0.5, 0.2, 0.05)
    Lw = a2.number_input("EWMA L", 2.0, 3.5, 2.962, 0.001, format="%.3f")
    k = a3.number_input("CUSUM k", 0.1, 1.5, 0.5, 0.1)
    h = a3.number_input("CUSUM h", 2.0, 8.0, 5.0, 0.5)
    res_arl = cached_arl(shift, lam, Lw, k, h, 1500)
    st.table(pd.Series(res_arl, name="average run length").map(lambda v: f"{v:,.1f}"))
    st.caption("Shewhart value is exact; EWMA and CUSUM values are averages of 1,500 simulated runs.")

    st.subheader("See it happen")
    seed = st.number_input("Random example #", 1, 9999, 7)
    rng = np.random.default_rng(int(seed))
    x = np.concatenate([rng.normal(0, 1, 30), rng.normal(shift, 1, 40)])
    i_res, _ = ql.imr(x, mu=0, sigma=1, rules="limits")
    e_res = ql.ewma(x, mu=0, sigma=1, lam=lam, L=Lw)
    c_res = ql.cusum(x, mu=0, sigma=1, k=k, h=h)
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True, gridspec_kw=dict(hspace=0.35))
    for ax, r, nm in zip(axes, (i_res, e_res, c_res), ("Individuals", "EWMA", "CUSUM")):
        plot_chart(r, ax, title=nm, show_zones=False, annotate=False)
        ax.axvline(30.5, color="#d03b3b", lw=1, ls=":")
    axes[0].text(30.7, axes[0].get_ylim()[0], " shift happens", color="#d03b3b", fontsize=8, va="bottom")
    st.pyplot(fig, width="stretch")
    det = []
    for nm, r in (("Individuals", i_res), ("EWMA", e_res), ("CUSUM", c_res)):
        idx = r.out_of_control
        after = idx[idx >= 30]
        before = idx[idx < 30]
        det.append(dict(chart=nm, false_alarms_before_shift=int(before.size),
                        points_until_detection=int(after[0] - 29) if after.size else "not detected"))
    st.table(pd.DataFrame(det).set_index("chart"))
    plt.close(fig)

# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------

with tab_help:
    st.markdown("""
### Reading a control chart
* The **center line** is the process average. The dashed **control limits** sit 3 standard errors above and below it.
  They describe what the process *does*, not what the customer *wants*: never confuse them with specification limits.
* Points inside the limits with no pattern = **common-cause** variation. Reacting to them (tweaking the process)
  usually makes things worse.
* A signal = evidence of a **special cause**: something specific changed. Find it, fix it, and prevent it.
* The shaded bands mark 1σ and 2σ. The run rules use them to catch patterns that never cross a limit.

### Phase I vs Phase II
* **Phase I**: look back at historical data, find and remove special causes, and settle on limits that describe the
  process when it is behaving.
* **Phase II**: freeze those limits and use them to watch new data as it arrives.

### Choosing a chart
| Data | Chart |
|---|---|
| Measurements in subgroups of 2–10 | X̄-R |
| Measurements in larger or unequal subgroups | X̄-S |
| One measurement per period | I-MR |
| Small, sustained shifts matter | EWMA or CUSUM |
| Defective / not defective, sample size varies | p (Laney p′ if samples are huge) |
| Defective count, constant sample size | np |
| Defects counted on a fixed unit | c |
| Defects per unit, unit size varies | u |
| Several related measurements | Hotelling T² |
""")
    st.markdown("### The run rules")
    st.table(pd.Series(RULE_DESCRIPTIONS, name="pattern"))
    st.caption("QualityLab is open source (MIT). Practice scenarios are simulated data.")
