"""Pareto analysis."""
from __future__ import annotations

import pandas as pd


def pareto(data, *, category: str | None = None, count: str | None = None,
           threshold: float = 0.8, other_below: float | None = None) -> pd.DataFrame:
    """Sort categories by frequency and compute cumulative shares.

    ``data`` may be: a Series/list of raw category labels (one per defect);
    a Series of counts indexed by category; or a DataFrame with ``category``
    (and optionally ``count``) columns.

    ``other_below`` folds categories with a share below this value into "Other",
    which is always placed last.

    The ``vital_few`` column marks the categories needed to reach ``threshold``
    (80 % by default) of the total.
    """
    if isinstance(data, pd.DataFrame):
        if category is None:
            raise ValueError("pass category= (and optionally count=) for a DataFrame")
        s = data.groupby(category)[count].sum() if count else data[category].value_counts()
    elif isinstance(data, pd.Series) and pd.api.types.is_numeric_dtype(data) and data.index.dtype == object:
        s = data.groupby(level=0).sum()
    else:
        s = pd.Series(list(data)).value_counts()
    s = s[s > 0].sort_values(ascending=False)
    if s.empty:
        raise ValueError("no positive counts")
    total = s.sum()
    if other_below is not None:
        small = s / total < other_below
        if small.sum() > 1:
            s = pd.concat([s[~small], pd.Series({"Other": s[small].sum()})])
    out = pd.DataFrame({"count": s})
    out["share"] = out["count"] / total
    out["cumulative_share"] = out["share"].cumsum()
    prev = out["cumulative_share"].shift(fill_value=0)
    out["vital_few"] = prev < threshold - 1e-12
    out.index.name = "category"
    return out
