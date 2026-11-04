"""“Be the quality manager”: choose a monitoring plan for the filling line.

The player picks from a small menu of plans (how often to check, how many
bottles, what decision rule, and whether to inspect everything before
shipping). Every plan in the menu is simulated with the Decision Studio
engine, so each choice can be scored against the best plan on the menu.
"""
from __future__ import annotations

from itertools import product

import pandas as pd

from ..scenarios import templates
from ..simulate import Policy, evaluate

EVERY = [1, 2, 4, 8]
SIZES = [2, 5]
RULES = {"spec": "Stop only if a bottle is out of spec", "shewhart": "Plot on a control chart (3σ limits)"}
FINALS = {"none": "Ship as made", "screen": "Weigh every bottle before shipping (100 % inspection)"}


def scenario():
    return templates()["filling"]


def menu_policies() -> list[Policy]:
    return [Policy(r, n=n, every_hours=h, L=3.0, final=f) for h, n, r, f in product(EVERY, SIZES, RULES, FINALS)]


def key(p: Policy) -> str:
    return f"{p.check}|{p.n}|{p.every_hours:g}|{p.final}"


def simulate_menu(reps: int = 300, years: float = 0.25, seed: int = 7) -> pd.DataFrame:
    t = scenario()
    pols = menu_policies() + [t.current]
    evs = evaluate(t.process, pols, reps=reps, years=years, seed=seed)
    rows = []
    for p, e in zip(pols, evs):
        s = e.summary()
        rows.append(dict(key=key(p), check=p.check, n=p.n, every_hours=p.every_hours, final=p.final,
                         plan=p.describe(t.process), annual_cost=s["annual_cost"], hours_to_fix=s["hours_to_fix"],
                         escapes_ppm=s["escapes_ppm"], false_alarms_per_week=s["false_alarms_per_week"],
                         is_today=(p is t.current),
                         **{f"part:{k}": float(v.mean()) for k, v in e.parts.items()}))
    df = pd.DataFrame(rows)
    today = df[df["is_today"]].iloc[0]
    df = df[~df["is_today"]].drop_duplicates("key").set_index("key")
    df.attrs["today"] = today.to_dict()
    best = df["annual_cost"].min()
    df["regret"] = df["annual_cost"] - best
    df["regret_pct"] = df["regret"] / best
    df["rank"] = df["annual_cost"].rank(method="min").astype(int)
    return df
