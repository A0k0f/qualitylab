"""qualitylab: statistical process control for teaching and practice."""
from . import arl, constants, datasets, plotting, rules
from .capability import CapabilityResult, capability
from .charts import c_chart, cusum, ewma, imr, np_chart, p_chart, subgroups_from_long, u_chart, xbar_r, xbar_s
from .multivariate import hotelling_t2
from .pareto import pareto
from .result import ChartResult

__version__ = "0.2.0"

__all__ = [
    "ChartResult", "CapabilityResult", "arl", "c_chart", "capability", "constants", "cusum",
    "datasets", "ewma", "hotelling_t2", "imr", "np_chart", "p_chart", "pareto", "plotting", "rules",
    "subgroups_from_long", "u_chart", "xbar_r", "xbar_s",
]
