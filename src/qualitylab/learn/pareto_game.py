"""Cost of quality and Pareto analysis: where should the improvement budget go?

Part 1 sorts costs into the four cost-of-quality categories (prevention,
appraisal, internal failure, external failure).

Part 2 gives a year of customer complaints for an online retailer. Ranked
by *count*, late deliveries come first; ranked by *cost*, wrong items do.

Part 3 is a budget problem: improvement projects each cut one complaint
category by a known share at a known cost, and the team has a fixed budget.
It is a small knapsack problem, so the best portfolio can be found exactly
and compared with common rules of thumb (biggest count first, best ratio
first).
"""
from __future__ import annotations

from itertools import combinations

import pandas as pd

COQ_CATEGORIES = ["Prevention", "Appraisal", "Internal failure", "External failure"]
COQ_ITEMS = [
    ("Designing error-proofing (poka-yoke) fixtures for an assembly step", "Prevention"),
    ("Training employees on a new work procedure", "Prevention"),
    ("Inspecting raw material when it arrives", "Appraisal"),
    ("Calibrating measuring instruments", "Appraisal"),
    ("Reworking defective units before they ship", "Internal failure"),
    ("Scrapping parts that fail final test", "Internal failure"),
    ("Handling warranty claims and product returns", "External failure"),
    ("Losing customers to a competitor after poor-quality deliveries", "External failure"),
]
COQ_WHY = {
    "Prevention": "Prevention costs are spent to stop defects from being made in the first place.",
    "Appraisal": "Appraisal costs are spent measuring and checking to find defects.",
    "Internal failure": "Internal failure costs arise from defects found before the customer receives the product.",
    "External failure": "External failure costs arise after a defect reaches the customer. They are usually the "
                        "largest, and partly hidden (lost goodwill, lost future sales).",
}

COMPLAINTS = pd.DataFrame(
    [
        ("Late delivery", 1200, 15),
        ("Wrong item shipped", 700, 45),
        ("Damaged packaging", 550, 30),
        ("Billing error", 400, 25),
        ("Website checkout bug", 300, 12),
        ("Rude or unhelpful support", 150, 60),
    ],
    columns=["category", "complaints_per_year", "cost_per_complaint"],
).set_index("category")
COMPLAINTS["annual_cost"] = COMPLAINTS["complaints_per_year"] * COMPLAINTS["cost_per_complaint"]

BUDGET = 40_000
PROJECTS = {
    "carrier": dict(label="Switch carriers and add delivery tracking", category="Late delivery", cost=25_000, cut=0.60),
    "scan": dict(label="Scan-to-verify at packing stations", category="Wrong item shipped", cost=15_000, cut=0.70),
    "packaging": dict(label="Redesign packaging for fragile items", category="Damaged packaging", cost=10_000, cut=0.60),
    "billing": dict(label="Automate invoice generation", category="Billing error", cost=8_000, cut=0.80),
    "bugfix": dict(label="Fix and test the checkout code", category="Website checkout bug", cost=3_000, cut=0.90),
    "coaching": dict(label="Coach support staff and add call scripts", category="Rude or unhelpful support",
                     cost=6_000, cut=0.50),
}


def project_table() -> pd.DataFrame:
    rows = []
    for k, p in PROJECTS.items():
        saving = COMPLAINTS.loc[p["category"], "annual_cost"] * p["cut"]
        rows.append(dict(key=k, project=p["label"], category=p["category"], cost=p["cost"],
                         cut=p["cut"], annual_saving=saving, saving_per_dollar=saving / p["cost"]))
    return pd.DataFrame(rows).set_index("key")


def evaluate(chosen: list[str] | set[str]) -> dict:
    t = project_table()
    chosen = [c for c in chosen if c in t.index]
    cost = float(t.loc[chosen, "cost"].sum()) if chosen else 0.0
    saving = float(t.loc[chosen, "annual_saving"].sum()) if chosen else 0.0
    return dict(chosen=sorted(chosen), cost=cost, annual_saving=saving, within_budget=cost <= BUDGET)


def optimal() -> dict:
    keys = list(PROJECTS)
    best = evaluate([])
    for r in range(1, len(keys) + 1):
        for combo in combinations(keys, r):
            e = evaluate(combo)
            if e["within_budget"] and e["annual_saving"] > best["annual_saving"] + 1e-9:
                best = e
    return best


def greedy(by: str) -> dict:
    """Rules of thumb: fund projects in order of 'count' (complaints), 'cost' (annual cost of the category)
    or 'ratio' (saving per dollar), skipping any that no longer fit."""
    t = project_table()
    if by == "count":
        order = t["category"].map(COMPLAINTS["complaints_per_year"]).sort_values(ascending=False).index
    elif by == "cost":
        order = t["category"].map(COMPLAINTS["annual_cost"]).sort_values(ascending=False).index
    elif by == "ratio":
        order = t["saving_per_dollar"].sort_values(ascending=False).index
    else:
        raise ValueError("by must be count, cost or ratio")
    chosen, spent = [], 0.0
    for k in order:
        if spent + t.loc[k, "cost"] <= BUDGET:
            chosen.append(k)
            spent += t.loc[k, "cost"]
    return evaluate(chosen)
