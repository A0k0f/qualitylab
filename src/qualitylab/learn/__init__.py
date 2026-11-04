"""Learning Lab: guided, game-like missions that teach quality management by doing.

Each mission is a self-contained module with the simulation logic and the
"ground truth" needed to score a player's predictions and decisions:

* :mod:`.redbeads`         Deming's Red Bead Experiment (the system vs. the worker)
* :mod:`.signals`          Signal or noise? (common vs. special causes, run rules)
* :mod:`.funnel`           Deming's funnel (tampering)
* :mod:`.capability_game`  Meeting a customer's Cpk requirement at least cost
* :mod:`.pareto_game`      Cost of quality and budgeting improvement projects
* :mod:`.manager_game`     Choosing a monitoring plan (uses the Decision Studio engine)
* :mod:`.concepts`         Pre/post concept check and end-of-lab survey
"""
from . import capability_game, concepts, funnel, manager_game, pareto_game, redbeads, signals

__all__ = ["capability_game", "concepts", "funnel", "manager_game", "pareto_game", "redbeads", "signals"]
