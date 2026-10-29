"""Editable business scenarios for the what-if simulator.

Each template is a realistic *starting point*: the numbers are illustrative,
not industry benchmarks. Users are expected to replace them with their own.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .decide import Investment
from .simulate import Costs, FailureMode, Policy, Process


@dataclass
class Template:
    key: str
    title: str
    industry: str
    pain: str
    process: Process
    current: Policy
    investments: list[Investment] = field(default_factory=list)
    max_escape_ppm: float | None = None
    max_false_alarms_per_week: float | None = None


def _filling() -> Template:
    p = Process(
        name="Cold-brew filling line", kind="measurement", unit_label="oz",
        description="A high-speed line fills 12-oz bottles. Underfilled bottles reaching retailers trigger "
                    "chargebacks and compliance risk; overfill is product given away.",
        units_per_hour=3600, hours_per_day=16, days_per_year=250,
        target=12.0, mean=12.10, sigma=0.05, lsl=11.88, usl=12.35,
        failure_modes=[
            FailureMode("Nozzle partly clogged", every_hours=80, shift=-0.12),
            FailureMode("Fill valve drifting", every_hours=160, drift_per_hour=-0.012),
            FailureMode("Pressure surges", every_hours=240, sigma_factor=2.0),
        ],
        notice_after_hours=16,
        costs=Costs(escape=1.50, internal=0.30, per_unit_tested=0.02, per_check=4, false_alarm=120,
                    repair=300, per_unit_screened=0.004, giveaway=0.06),
        inspection_effectiveness=0.98,
    )
    return Template(
        "filling", "Beverage filling line", "Food & beverage",
        "We overfill to stay safe, still get short-fill chargebacks, and nobody knows how often to check.",
        p, Policy("spec", n=5, every_hours=4),
        [Investment("Servo filler upgrade (30 % less variation)", 40_000, variation_factor=0.7),
         Investment("Nozzle cleaning every shift (problems half as often)", 15_000, frequency_factor=0.5)],
        max_false_alarms_per_week=3,
    )


def _cnc() -> Template:
    p = Process(
        name="CNC shaft machining", kind="measurement", unit_label="mm",
        description="A CNC lathe turns shafts for an automotive customer. A bad shaft found at the customer "
                    "means a claim and possibly a line stoppage.",
        units_per_hour=60, hours_per_day=16, days_per_year=250,
        target=25.000, mean=25.004, sigma=0.010, lsl=24.950, usl=25.050,
        failure_modes=[
            FailureMode("Tool wear", every_hours=80, drift_per_hour=0.0025),
            FailureMode("Chipped insert", every_hours=120, shift=0.03),
            FailureMode("Thermal growth after restart", every_hours=80, shift=-0.02),
        ],
        notice_after_hours=16,
        costs=Costs(escape=250, internal=25, per_unit_tested=1.5, per_check=5, false_alarm=90, repair=150,
                    per_unit_screened=2.0),
        inspection_effectiveness=0.95,
    )
    return Template(
        "cnc", "CNC machined parts", "Manufacturing",
        "Customer claims are expensive, gauging is slow, and operators argue about when to change the tool.",
        p, Policy("spec", n=1, every_hours=1),
        [Investment("Automatic tool-wear compensation", 12_000, frequency_factor=0.6),
         Investment("Better coolant temperature control (drift problems smaller)", 8_000, size_factor=0.7)],
        max_escape_ppm=500,
    )


def _picking() -> Template:
    p = Process(
        name="E-commerce order picking", kind="pass_fail",
        description="A fulfillment center picks and packs customer orders. A wrong or missing item means a "
                    "return, a reshipment, a support contact and an unhappy customer.",
        units_per_hour=400, hours_per_day=16, days_per_year=300, defect_rate=0.006,
        failure_modes=[
            FailureMode("New temporary pickers", every_hours=240, rate_factor=2.5),
            FailureMode("Bin locations mislabeled", every_hours=480, rate_factor=5.0),
            FailureMode("Scanner sync outage", every_hours=960, rate_factor=8.0),
        ],
        notice_after_hours=24,
        costs=Costs(escape=28, internal=3, per_unit_tested=0.80, per_check=2, false_alarm=60, repair=200,
                    per_unit_screened=0.45),
        inspection_effectiveness=0.95,
    )
    return Template(
        "picking", "Warehouse order accuracy", "Retail & logistics",
        "Audits keep flagging problems that turn out to be nothing, while real mis-pick waves slip through.",
        p, Policy("spec", n=50, every_hours=8),
        [Investment("Pick-to-light system (baseline errors −60 %)", 120_000, defect_rate_factor=0.4),
         Investment("Structured onboarding for temps (problems half as big)", 20_000, size_factor=0.5)],
        max_false_alarms_per_week=3,
    )


def _pharmacy() -> Template:
    p = Process(
        name="Hospital pharmacy dispensing", kind="pass_fail",
        description="A central pharmacy fills medication orders around the clock. A dispensing error that "
                    "reaches a patient carries a large expected cost (harm, extra care, liability).",
        units_per_hour=50, hours_per_day=24, days_per_year=365, defect_rate=0.002,
        failure_modes=[
            FailureMode("Look-alike drug stocked in the wrong bin", every_hours=500, rate_factor=10.0),
            FailureMode("Night-shift understaffing", every_hours=240, rate_factor=3.0),
        ],
        notice_after_hours=48,
        costs=Costs(escape=2500, internal=8, per_unit_tested=3, per_check=5, false_alarm=100, repair=300,
                    per_unit_screened=1.50),
        inspection_effectiveness=0.90,
    )
    return Template(
        "pharmacy", "Pharmacy dispensing safety", "Healthcare",
        "Is a full second check of every order worth its cost, and how do we catch error waves early?",
        p, Policy("none", final="screen"),
        [Investment("Barcode scanning at dispensing (baseline errors −50 %)", 60_000, defect_rate_factor=0.5)],
        max_escape_ppm=500,
    )


def _invoices() -> Template:
    p = Process(
        name="Accounts-payable invoice processing", kind="pass_fail",
        description="An AP team keys and approves supplier invoices. Errors that get paid are expensive to "
                    "recover; month-end reconciliation eventually exposes error waves.",
        units_per_hour=30, hours_per_day=8, days_per_year=250, defect_rate=0.02,
        failure_modes=[
            FailureMode("Vendor master data errors", every_hours=240, rate_factor=3.0),
            FailureMode("ERP update bug", every_hours=800, rate_factor=5.0),
        ],
        notice_after_hours=80,
        costs=Costs(escape=85, internal=12, per_unit_tested=4, per_check=5, false_alarm=80, repair=500,
                    per_unit_screened=3.5),
        inspection_effectiveness=0.85,
    )
    return Template(
        "invoices", "Invoice processing errors", "Finance & shared services",
        "We audit a few invoices a day, find something almost every time, and still overpay suppliers.",
        p, Policy("spec", n=5, every_hours=40),
        [Investment("OCR + three-way-match automation (baseline errors −50 %)", 30_000, defect_rate_factor=0.5)],
    )


def _supplier() -> Template:
    p = Process(
        name="Incoming supplier parts", kind="pass_fail",
        description="Molded housings arrive from a supplier in daily lots. A bad part reaching assembly costs "
                    "rework and sometimes a line stop.",
        units_per_hour=500, hours_per_day=8, days_per_year=250, defect_rate=0.004,
        failure_modes=[
            FailureMode("Supplier resin batch problem", every_hours=200, rate_factor=8.0),
            FailureMode("Mold cavity damage", every_hours=400, rate_factor=4.0),
        ],
        notice_after_hours=40,
        costs=Costs(escape=40, internal=0.6, per_unit_tested=0.5, per_check=3, false_alarm=50, repair=250,
                    per_unit_screened=0.25),
        inspection_effectiveness=0.90, lot_hours=8,
    )
    return Template(
        "supplier", "Incoming inspection of supplier lots", "Procurement & supplier quality",
        "Our sampling plan was inherited from years ago. Are we inspecting too much, too little, or the wrong way?",
        p, Policy("none", final="lots", lot_n=80, lot_c=2),
        [Investment("Supplier development program (problems half as often)", 25_000, frequency_factor=0.5)],
    )


_BUILDERS = [_filling, _cnc, _picking, _pharmacy, _invoices, _supplier]


def templates() -> dict[str, Template]:
    """Fresh copies of all templates (safe to edit)."""
    return {t.key: t for t in (b() for b in _BUILDERS)}
