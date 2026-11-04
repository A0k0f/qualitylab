"""Concept check (pre/post) and end-of-lab survey items.

The concept check has 12 multiple-choice items, each paired with a
confidence rating. The same items are used before and after the missions,
in a shuffled order; feedback is given only after the post-check so the
pre-check does not teach to the test.

Items are original and written for this tool. Before using scores in a
publication, they should be reviewed by the course instructor and
piloted (item difficulty, discrimination, internal consistency).

The usability survey is the System Usability Scale (SUS; Brooke, 1996),
used here with its standard wording and scoring.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Item:
    id: str
    concept: str
    mission: str
    stem: str
    options: tuple[str, ...]
    answer: int
    why: str


ITEMS: tuple[Item, ...] = (
    Item("C01", "Common vs. special causes", "signals",
         "A call center's average daily wait time has stayed inside its control limits for six months, varying "
         "between 3 and 6 minutes. A manager wants to investigate every day above 5 minutes. What is the best response?",
         ("Investigate each high day to find its cause",
          "Leave the day-to-day ups and downs alone; to reduce them, change the system (staffing, procedures)",
          "Tighten the control limits so more days are flagged",
          "Reward the staff on days below 4 minutes"), 1,
         "Points inside the limits with no pattern are common-cause variation. Chasing individual days wastes effort; "
         "lowering the average or the spread requires changing the system itself."),
    Item("C02", "Control limits vs. specification limits", "capability",
         "Control limits on a control chart are calculated from:",
         ("The customer's requirements", "The process's own data", "Management's targets",
          "The engineering drawing"), 1,
         "Control limits are the voice of the process (computed from its data). Specification limits are the voice "
         "of the customer."),
    Item("C03", "Statistical control", "capability",
         "A process is in statistical control. This means that:",
         ("All of its output meets specifications", "Its variation is stable and predictable",
          "Its Cpk is at least 1.33", "No further improvement is needed"), 1,
         "In control means only common-cause variation is present, so the process is predictable. It can still "
         "produce output that fails the customer's specifications."),
    Item("C04", "Tampering", "funnel",
         "An operator adjusts a machine after every unit to bring the last measurement back to target. The process "
         "was in control before. What happens?",
         ("Variation decreases", "Nothing changes", "Variation increases",
          "The average moves permanently away from target"), 2,
         "Reacting to common-cause variation adds the adjustment's randomness to the process. Deming's funnel shows "
         "the variance doubles."),
    Item("C05", "Deming and the system", "redbeads",
         "According to Deming, most quality problems are the responsibility of:",
         ("Front-line workers", "Management and the system they create", "Suppliers", "Customers"), 1,
         "Deming estimated that about 94 % of problems belong to the system, which only management can change. "
         "The Red Bead Experiment makes this visible."),
    Item("C06", "Cp vs. Cpk", "capability",
         "A process has Cp = 1.5 and Cpk = 0.9. What is the most likely issue?",
         ("Its variation is too large", "It is not centered between the specification limits",
          "It is out of statistical control", "Its specification limits are too wide"), 1,
         "Cp compares spread with the tolerance; Cpk also accounts for where the process is centered. A large gap "
         "between them means the spread is fine but the process is off-center."),
    Item("C07", "Run rules", "signals",
         "On a control chart, the last 8 points are all above the center line, yet all are inside the control "
         "limits. This suggests:",
         ("Nothing; every point is within the limits", "A likely shift in the process average",
          "The control limits are too wide", "A measurement error on the last point"), 1,
         "Eight points in a row on one side would happen by chance less than 1 % of the time. It is a classic "
         "signal of a shift, even though no single point is beyond a limit."),
    Item("C08", "Pareto analysis", "pareto",
         "Pareto analysis helps a team to:",
         ("Find the root cause of a problem", "Focus on the few categories that account for most of the problem",
          "Monitor a process over time", "Show the correlation between two variables"), 1,
         "A Pareto chart ranks categories so effort goes to the vital few. Root causes need other tools, such as "
         "cause-and-effect diagrams."),
    Item("C09", "Cost of quality", "pareto",
         "Which of these is a prevention cost?",
         ("Inspecting incoming material", "Reworking defective units",
          "Training employees on a new procedure", "Handling warranty claims"), 2,
         "Training stops defects before they happen. Inspection is appraisal, rework is internal failure and "
         "warranty claims are external failure."),
    Item("C10", "Inspection vs. capability", "capability",
         "A plant adds 100 % final inspection. Which statement is true?",
         ("Cpk increases", "Fewer defects reach customers, but the process still makes just as many",
          "The process becomes in control", "Appraisal costs fall"), 1,
         "Inspection sorts output; it does not change what the process makes. You pay to find defects instead of "
         "preventing them."),
    Item("C11", "Regression to the mean", "redbeads",
         "A manager praises the top salesperson each month and notices that person usually does worse the next "
         "month. The most likely explanation is:",
         ("Praise makes people complacent", "An extreme month is usually followed by a more typical one",
          "Colleagues work harder to catch up", "The sales target was too easy"), 1,
         "When results vary at random, the top performer in one period is usually followed by a more average one, "
         "whatever the manager does. This is regression to the mean."),
    Item("C12", "Economics of monitoring", "manager",
         "Checking a process more often:",
         ("Always lowers total quality cost",
          "Catches problems sooner but adds checking costs and false alarms; the best frequency balances these",
          "Has no effect on false alarms", "Only matters in manufacturing"), 1,
         "More frequent checks shorten the time problems go unnoticed, but every check costs money and adds a "
         "chance of a false alarm. The best plan balances these costs."),
)
ITEM_BY_ID = {i.id: i for i in ITEMS}


def order(seed: int) -> list[str]:
    rng = np.random.default_rng(seed)
    ids = [i.id for i in ITEMS]
    rng.shuffle(ids)
    return ids


def score(answers: dict[str, int]) -> dict:
    correct = {k: int(v == ITEM_BY_ID[k].answer) for k, v in answers.items() if k in ITEM_BY_ID}
    n = len(ITEMS)
    return dict(correct=correct, score=sum(correct.values()), n=n, pct=sum(correct.values()) / n)


def normalized_gain(pre_pct: float, post_pct: float) -> float:
    """Hake's normalized gain <g> = (post − pre) / (1 − pre)."""
    if pre_pct >= 1:
        return float("nan")
    return (post_pct - pre_pct) / (1 - pre_pct)


# --- end-of-lab survey -------------------------------------------------------

SUS_ITEMS = (
    "I think that I would like to use this system frequently.",
    "I found the system unnecessarily complex.",
    "I thought the system was easy to use.",
    "I think that I would need the support of a technical person to be able to use this system.",
    "I found the various functions in this system were well integrated.",
    "I thought there was too much inconsistency in this system.",
    "I would imagine that most people would learn to use this system very quickly.",
    "I found the system very cumbersome to use.",
    "I felt very confident using the system.",
    "I needed to learn a lot of things before I could get going with this system.",
)


def sus_score(responses: list[int]) -> float:
    """SUS score 0-100 from ten 1-5 responses (Brooke, 1996)."""
    if len(responses) != 10:
        raise ValueError("SUS needs 10 responses")
    tot = sum((r - 1) if i % 2 == 0 else (5 - r) for i, r in enumerate(responses))
    return tot * 2.5


LEARNING_ITEMS = (
    ("L1", "The Learning Lab helped me understand the difference between common-cause and special-cause variation."),
    ("L2", "Making a prediction before seeing the result helped me learn."),
    ("L3", "I now understand why reacting to every data point can make a process worse."),
    ("L4", "I could explain to a manager why a process can be in control and still not satisfy customers."),
    ("L5", "The missions felt connected to real business decisions."),
    ("L6", "I would recommend the Learning Lab to students in future sections of this course."),
)
LIKERT5 = ("Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree")
