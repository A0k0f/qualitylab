"""End-to-end: a student plays the whole Learning Lab (consent, every mission, both checks, survey).

Runs headlessly with Streamlit's AppTest in research mode with a local JSON-lines store, once per
experimental condition, then checks that the logged data feed the analysis pipeline.
"""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from qualitylab import research, research_analysis  # noqa: E402
from qualitylab.learn import concepts as C  # noqa: E402
from qualitylab.learn import pareto_game as PG  # noqa: E402

PAGE = str(Path(__file__).resolve().parents[1] / "app" / "views" / "learning_lab.py")
SALT = "s" * 20


class Player:
    def __init__(self, at):
        self.at = at

    def ok(self, where):
        assert not self.at.exception, (where, [e.value for e in self.at.exception])

    def click(self, start, i=0):
        bs = [b for b in self.at.button if b.label.startswith(start)]
        assert bs, (start, [b.label for b in self.at.button])
        bs[i].click().run()
        self.ok(start)

    def key(self, k):
        b = [x for x in self.at.button if x.key == k]
        assert b, (k, [x.key for x in self.at.button])
        b[0].click().run()
        self.ok(k)

    def has(self, start):
        return any(b.label.startswith(start) for b in self.at.button)


def play_everything(at, letters: str) -> None:
    p = Player(at)
    # consent and anonymous code
    at.checkbox(key="consent_adult").check().run()
    p.click("✅ I agree")
    for ti, v in zip(at.text_input, [letters, "07", "BO"]):
        ti.set_value(v)
    p.click("Create my code")
    predicting = at.session_state["lab"]["condition"] != "no_predict"

    # warm-up check
    p.key("go_pre")
    for it in C.ITEMS:
        at.radio(key=f"pre_{it.id}").set_value((it.answer + 1) % len(it.options) if it.id < "C04" else it.answer)
    p.click("Submit")
    p.click("Go to the missions")

    # red beads
    p.key("go_redbeads")
    for w in ("Maria", "Jamal", "Wei", "Priya", "Tom", "Sofia"):
        at.selectbox(key=f"rb_act_1_{w}").set_value("Warning" if w == "Jamal" else "No action")
    if predicting:
        at.selectbox(key="rb_pred_best").set_value("Wei")
        at.number_input(key="rb_pred_total").set_value(60)
    p.click("Run Day 2")
    p.click("Run Day 3")
    p.click("Continue")
    at.radio[0].set_value(1)
    p.click("See what really happened")
    p.click("Now fix the system")
    at.radio[0].set_value("supplier")
    if predicting:
        at.number_input(key="rb_pred_change").set_value(25)
    p.click("Run four more days")
    p.click("Last step")
    at.text_area[0].set_value("Reward improving the system.")
    p.click("Finish mission")
    p.click("← Back to all missions")

    # signal or noise
    p.key("go_signals")
    p.click("Start Round 1")
    for phase in ("A", "B"):
        for k in range(8):
            at.radio[0].set_value("Investigate (costs $300)" if k % 2 == 0 else "Leave it alone")
            p.click("Decide")
            p.click("Next chart" if k < 7 else "Finish this round")
        if phase == "A":
            p.click("Start Round 2")
    at.text_area[0].set_value("Look for patterns.")
    p.click("Finish mission")
    p.click("← Back to all missions")

    # funnel
    p.key("go_funnel")
    if predicting:
        at.radio[0].set_value(0)
    p.click("Start filling")
    for k in range(14):
        at.number_input(key=f"fn_adj_{k}").set_value(0.05 if k % 2 else -0.05)
        p.click("Fill the next bottle")
    p.click("See how you did")
    p.click("Compare four strategies")
    if predicting:
        at.radio[0].set_value(1)
        p.click("Run all four")
    p.click("Last step")
    at.radio[0].set_value(1)
    p.click("Finish mission")
    p.click("← Back to all missions")

    # capability
    p.key("go_capability")
    if predicting:
        at.radio[0].set_value(2)
        at.radio[1].set_value("No")
    p.click("Show me")
    p.click("Practice")
    for r in at.radio:
        r.set_value("Yes")
    p.click("Check my answers")
    p.click("Now save the contract")
    for cb in at.checkbox:
        if cb.key.endswith("_inspect"):
            cb.check()
    p.click("Try it")
    for cb in at.checkbox:
        if cb.key.endswith(("_center", "_tooling")):
            cb.check()
    p.click("Try it")
    p.click("Last step")
    at.radio[0].set_value(1)
    p.click("Finish mission")
    p.click("← Back to all missions")

    # pareto
    p.key("go_pareto")
    for sb in at.selectbox:
        sb.set_value(PG.COQ_ITEMS[int(sb.key.split("_")[1])][1])
    p.click("Check")
    p.click("Next: the complaints data")
    if predicting:
        at.radio[0].set_value("Late delivery")
        p.click("Show the Pareto")
    p.click("Next: spend the budget")
    for cb in at.checkbox:
        if cb.key.split("_")[-1] in ("carrier", "scan"):
            cb.check()
    p.click("Fund these")
    for cb in at.checkbox:
        if cb.key.split("_")[-1] in ("scan", "packaging", "billing", "coaching"):
            cb.check()
    p.click("Fund these")
    p.click("Last step")
    at.text_area[0].set_value("Cost, not count.")
    p.click("Finish mission")
    p.click("← Back to all missions")

    # quality manager
    p.key("go_manager")
    if predicting:
        at.number_input[0].set_value(150000)
    p.click("Design my plan")
    p.click("Simulate a year")
    at.radio(key="mg_r1").set_value("shewhart")
    at.radio(key="mg_n1").set_value(5)
    at.select_slider(key="mg_e1").set_value(2)
    p.click("Simulate a year")
    if not p.has("See the verdict"):
        p.click("Simulate a year")
    p.click("See the verdict")
    at.text_area[0].set_value("Inspection sorts; it does not prevent.")
    p.click("Finish mission")
    p.click("← Back to all missions")

    # final check and survey
    p.key("go_post")
    for it in C.ITEMS:
        at.radio(key=f"post_{it.id}").set_value(it.answer)
    p.click("Submit")
    p.click("Continue to the short feedback")
    for i in range(10):
        at.radio(key=f"sus{i}").set_value(4 if i % 2 == 0 else 2)
    keys = {r.key for r in at.radio}
    assert ("learn_L2" in keys) == predicting  # the item about predicting is only asked when students predicted
    for k, _ in C.LEARNING_ITEMS:
        if f"learn_{k}" in keys:
            at.radio(key=f"learn_{k}").set_value(4)
    p.click("Submit feedback")


@pytest.mark.parametrize("letters,condition", [("MA", "predict"), ("PA", "no_predict")])
def test_full_learning_lab_in_research_mode(tmp_path, letters, condition):
    log = tmp_path / "events.jsonl"
    at = AppTest.from_file(PAGE, default_timeout=240)
    at.secrets["research"] = dict(enabled=True, irb_protocol="TEST-1", pi_name="PI", pi_email="pi@x.edu",
                                  backend="local", local_path=str(log), salt=SALT,
                                  conditions=["predict", "no_predict"], course_code="TEST")
    at.run()
    assert any("research study" in s.value for s in at.subheader)
    play_everything(at, letters)

    lab = at.session_state["lab"]
    assert lab["condition"] == condition
    assert set(lab["done"]) == {"redbeads", "signals", "funnel", "capability", "pareto", "manager"}
    assert lab["post"]["score"] == 12 and lab["pre"]["score"] == 9

    cfg = research.ResearchConfig.from_mapping(dict(at.secrets["research"]))
    research.get_sink(cfg).flush()
    events = research.LocalBackend(str(log)).read()
    assert len(events) == len(lab["record"])
    assert all(e["participant_id"] == lab["pid"] for e in events)
    n_pred = sum(e["event_type"] == "prediction" for e in events)
    assert (n_pred > 0) == (condition == "predict")

    p = research_analysis.participants(events).iloc[0]
    assert p["pre_score"] == pytest.approx(0.75) and p["post_score"] == 1.0
    assert all(p[f"{m}_done"] for m in ("redbeads", "signals", "funnel", "capability", "pareto", "manager"))
    assert p["rb_system_cause"] and p["rb_chose_supplier"] and p["cap_found_cheapest"]
    assert p["pg_first_share_of_optimal"] < 1 and p["pg_best_share_of_optimal"] == pytest.approx(1)
    assert p["mg_best_regret_pct"] == pytest.approx(0)
    assert p["sus"] == 75
    rb = research_analysis.redbeads_debrief(events)
    assert rb["n"] == 1 and 0 <= rb["worst_day2"] <= 50
    sc = research_analysis.signals_by_category(events)
    assert sc.shape == (4, 2) and sc.notna().all().all()


def test_nothing_is_stored_without_consent(tmp_path):
    log = tmp_path / "events.jsonl"
    at = AppTest.from_file(PAGE, default_timeout=120)
    at.secrets["research"] = dict(enabled=True, irb_protocol="TEST-1", pi_name="PI", pi_email="pi@x.edu",
                                  backend="local", local_path=str(log), salt=SALT)
    at.run()
    Player(at).click("No thanks")
    Player(at).key("go_redbeads")
    assert at.session_state["lab"]["record"], "the student's own record still works"
    assert not log.exists()


def test_no_research_config_means_no_consent_screen():
    at = AppTest.from_file(PAGE, default_timeout=120)
    at.run()
    assert not at.exception
    assert any(t.value.endswith("Learning Lab") for t in at.title)
    assert not any("research study" in s.value for s in at.subheader)
