"""The object every chart function returns."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ChartResult:
    """A computed control chart.

    Attributes
    ----------
    name : str
        Chart type, e.g. ``"Xbar"``, ``"R"``, ``"p"``, ``"EWMA"``.
    statistic : ndarray
        The plotted statistic, one value per subgroup/observation.
    center, ucl, lcl : ndarray
        Center line and control limits, same length as ``statistic``
        (constant limits are simply repeated; variable limits vary).
    sigma : ndarray
        Standard error of the plotted statistic at each point, used for the
        zone (1σ/2σ) rules. ``(ucl - center) / L`` for Shewhart charts.
    labels : Index
        Subgroup labels (dates, batch IDs, or 1..m).
    phase1 : ndarray[bool]
        True for points used to estimate the limits (Phase I / calibration).
    excluded : ndarray[bool]
        Phase I points that were dropped when estimating the limits.
    violations : dict[int, ndarray[int]]
        Rule number -> positions of points that signal under that rule.
    params : dict
        Estimated parameters (mean, sigma, L, subgroup sizes, ...).
    """

    name: str
    statistic: np.ndarray
    center: np.ndarray
    ucl: np.ndarray
    lcl: np.ndarray
    sigma: np.ndarray
    labels: pd.Index
    phase1: np.ndarray
    excluded: np.ndarray = field(default=None)  # type: ignore[assignment]
    violations: dict[int, np.ndarray] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    kind: str = "shewhart"

    def __post_init__(self) -> None:
        m = len(self.statistic)
        if self.excluded is None:
            self.excluded = np.zeros(m, dtype=bool)
        for k in ("center", "ucl", "lcl", "sigma"):
            v = np.asarray(getattr(self, k), dtype=float)
            if v.ndim == 0:
                v = np.full(m, float(v))
            setattr(self, k, v)

    # ------------------------------------------------------------------
    @property
    def out_of_control(self) -> np.ndarray:
        """Positions flagged by *any* active rule (sorted, unique)."""
        if not self.violations:
            return np.array([], dtype=int)
        return np.unique(np.concatenate([np.asarray(v, int) for v in self.violations.values()]))

    @property
    def in_control(self) -> bool:
        return self.out_of_control.size == 0

    def first_signal(self, phase2_only: bool = False) -> int | None:
        idx = self.out_of_control
        if phase2_only:
            idx = idx[~self.phase1[idx]]
        return int(idx[0]) if idx.size else None

    def to_frame(self) -> pd.DataFrame:
        """One row per point, including which rules each point violates."""
        rules_per_point: list[str] = [""] * len(self.statistic)
        for rule in sorted(self.violations):
            for i in self.violations[rule]:
                rules_per_point[i] = (rules_per_point[i] + f",{rule}").lstrip(",")
        df = pd.DataFrame(
            {
                self.name: self.statistic,
                "CL": self.center,
                "UCL": self.ucl,
                "LCL": self.lcl,
                "phase": np.where(self.phase1, "I", "II"),
                "excluded_from_limits": self.excluded,
                "rules_violated": rules_per_point,
            },
            index=self.labels,
        )
        for k, v in self.extra.items():
            if isinstance(v, np.ndarray) and v.shape == self.statistic.shape:
                df[k] = v
        return df

    def summary(self) -> str:
        from .rules import RULE_DESCRIPTIONS

        n_used = int((self.phase1 & ~self.excluded).sum())
        lines = [f"{self.name} chart: {len(self.statistic)} points, limits from {n_used}"
                 + (f" (Phase I = first {int(self.phase1.sum())}" if (~self.phase1).any() else " (all points")
                 + (f", {int(self.excluded.sum())} excluded)" if self.excluded.any() else ")")]
        cl = np.unique(np.round(self.center, 10))
        if cl.size == 1:
            lines.append(f"  CL = {cl[0]:.6g}")
        if np.unique(np.round(self.ucl, 10)).size == 1:
            lines.append(f"  UCL = {self.ucl[0]:.6g}   LCL = {self.lcl[0]:.6g}")
        else:
            lines.append("  limits vary with subgroup size")
        if self.in_control:
            lines.append("  No signals: the process appears in statistical control.")
        else:
            for rule in sorted(self.violations):
                pts = [str(self.labels[i]) for i in self.violations[rule]]
                if pts:
                    lines.append(f"  Rule {rule} ({RULE_DESCRIPTIONS.get(rule, '')}): {', '.join(pts)}")
        return "\n".join(lines)

    def plot(self, ax=None, **kwargs):
        from .plotting import plot_chart

        return plot_chart(self, ax=ax, **kwargs)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<ChartResult {self.name}: {len(self.statistic)} pts, {self.out_of_control.size} flagged>"
