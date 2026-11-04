"""End-to-end: a student plays the whole Learning Lab (consent, every mission, both checks, survey).

Runs headlessly with Streamlit's AppTest in research mode with a local JSON-lines store, once per
experimental condition, then checks that the logged data feed the analysis pipeline.
"""
import json
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

    # process lab: three experiments (new, re-run, one setting changed), a replication and a note
    play_process_lab(at, predicting)

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


def play_process_lab(at, predicting: bool) -> None:
    p = Player(at)
    p.key("go_processlab")
    at.selectbox(key="pl_example").set_value("Filling bottles (oz)").run()
    at.selectbox(key="pl_new_kind").set_value("shift").run()
    p.click("➕ Add this change")
    assert at.number_input(key="pl_c_size_1").value == pytest.approx(0.04)

    def predict(k):
        if predicting:
            at.radio(key=f"pl_p_det_{k}").set_value("Yes")
            at.number_input(key=f"pl_p_delay_{k}").set_value(4)
            at.number_input(key=f"pl_p_fa_{k}").set_value(1)
            at.number_input(key=f"pl_p_oos_{k}").set_value(0.1)
        else:
            assert not [r for r in at.radio if r.key and r.key.startswith("pl_p_")]

    predict(1)
    p.click("▶ Run experiment")
    assert any(m.label == "False alarms" for m in at.metric)
    p.click("📊 Run it 200 times")
    assert any(m.label.startswith("False alarms per 100") for m in at.metric)
    p.click("🔁 Same settings")
    at.slider(key="pl_n").set_value(8).run()
    predict(3)
    p.click("▶ Run experiment")
    [t for t in at.text_area if t.label.startswith("What did this experiment teach you")][0].set_value(
        "A bigger sample caught it sooner.")
    p.click("Save my note")
    p.click("✅ Finish Process Lab")
    assert "processlab" in at.session_state["lab"]["done"]
    p.click("← Learning Lab")


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
    assert set(lab["done"]) == {"processlab", "redbeads", "signals", "funnel", "capability", "pareto", "manager"}
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
    assert all(p[f"{m}_done"] for m in ("processlab", "redbeads", "signals", "funnel", "capability", "pareto",
                                         "manager"))
    x = research_analysis.experiments(events)
    assert list(x["exp"]) == [1, 2, 3] and list(x["kind"]) == ["new", "rerun", "new"]
    assert x.loc[2, "changed"] == "process.n" and x.loc[2, "n"] == 8 and x.loc[0, "replicated"]
    assert x.loc[2, "reflection"] == "A bigger sample caught it sooner."
    assert x["detected"].notna().all() and x["cost_total"].gt(0).all()
    assert (x["pred_detect"].notna().sum() > 0) == (condition == "predict")
    assert p["pl_experiments"] == 3 and p["pl_one_factor_share"] == 1.0 and p["pl_replications"] == 1
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


INSTRUCTOR = str(Path(__file__).resolve().parents[1] / "app" / "views" / "instructor.py")


def test_instructor_page_is_locked_without_a_password():
    at = AppTest.from_file(INSTRUCTOR, default_timeout=120)
    at.run()
    assert not at.exception
    assert not at.tabs and not at.metric and not at.radio, "nothing but the lock notice may show"


def test_instructor_page_needs_the_right_password():
    at = AppTest.from_file(INSTRUCTOR, default_timeout=120)
    at.secrets["instructor_password"] = "correct horse"
    at.run()
    assert not at.tabs
    at.text_input[0].set_value("wrong")
    at.button[0].click().run()
    assert not at.tabs and any("Wrong password" in e.value for e in at.error)
    at.text_input[0].set_value("correct horse")
    at.button[0].click().run()
    assert not at.exception and not at.tabs                      # participation view first (off here)
    assert any("participation record is **off**" in i.value for i in at.info)
    at.radio[0].set_value(at.radio[0].options[1]).run()          # research view: synthetic preview
    assert not at.exception and len(at.tabs) == 5


def test_participation_record_is_named_and_kept_apart_from_research(tmp_path):
    teach, res = tmp_path / "teach.jsonl", tmp_path / "research.jsonl"
    at = AppTest.from_file(PAGE, default_timeout=120)
    at.secrets["teaching"] = dict(enabled=True, backend="local", local_path=str(teach), course_code="POM445",
                                  identify="name")
    at.secrets["research"] = dict(enabled=True, irb_protocol="TEST-1", pi_name="PI", pi_email="pi@x.edu",
                                  backend="local", local_path=str(res), salt=SALT)
    at.run()
    assert any("Participation sign-in" in h.value for h in at.subheader)
    p = Player(at)
    p.click("Continue")                                   # empty name is refused
    assert at.error and not at.session_state["lab"]["student"]
    at.text_input[0].set_value("  Ada   Lovelace ")
    p.click("Continue")
    assert any("research study" in h.value for h in at.subheader)  # then the (separate) research consent
    at.checkbox(key="consent_adult").check().run()
    p.click("✅ I agree")
    for ti, v in zip(at.text_input, ["MA", "07", "BO"]):
        ti.set_value(v)
    p.click("Create my code")
    play_process_lab(at, at.session_state["lab"]["condition"] != "no_predict")
    from qualitylab import teaching
    lab = at.session_state["lab"]
    teaching.get_sink(teaching.TeachingConfig.from_mapping(dict(at.secrets["teaching"]))).flush()
    research.get_sink(research.ResearchConfig.from_mapping(dict(at.secrets["research"]))).flush()
    t_ev, r_ev = research.LocalBackend(str(teach)).read(), research.LocalBackend(str(res)).read()
    assert t_ev and r_ev
    assert {e["student"] for e in t_ev} == {"Ada Lovelace"} and {e["course_code"] for e in t_ev} == {"POM445"}
    assert all("participant_id" not in e and "condition" not in e for e in t_ev)
    assert not any(lab["pid"] in json.dumps(e) for e in t_ev)          # no research code in the teaching record
    assert not any("Lovelace" in json.dumps(e) for e in r_ev)          # no name in the research data
    T = teaching.participation(t_ev)
    assert T.loc[0, "student"] == "Ada Lovelace" and T.loc[0, "process_lab_experiments"] == 3
    assert T.loc[0, "process_lab_finished"]


def test_participation_summary_mode_keeps_no_inputs(tmp_path):
    teach = tmp_path / "teach.jsonl"
    at = AppTest.from_file(PAGE, default_timeout=120)
    at.secrets["teaching"] = dict(enabled=True, backend="local", local_path=str(teach), detail="summary")
    at.run()
    assert any("Participation code" in h.value for h in at.subheader)
    at.text_input[0].set_value("no!")
    Player(at).click("Continue")
    assert at.error and not at.session_state["lab"]["student"]
    at.text_input[0].set_value(" ql-7f3k2 ")
    Player(at).click("Continue")
    play_process_lab(at, True)
    from qualitylab import teaching
    teaching.get_sink(teaching.TeachingConfig.from_mapping(dict(at.secrets["teaching"]))).flush()
    t_ev = research.LocalBackend(str(teach)).read()
    assert t_ev and all(e["response"] == "" and e["detail"] == "" and e["score"] == "" for e in t_ev)
    assert {e["student"] for e in t_ev} == {"QL-7F3K2"}
    T = teaching.participation(t_ev, {"QL-7F3K2": "Grace Hopper"})
    assert T.loc[0, "process_lab_experiments"] == 3 and T.loc[0, "name"] == "Grace Hopper"


def test_instructor_participation_view(tmp_path):
    from qualitylab import teaching
    teach = tmp_path / "teach.jsonl"
    cfg = teaching.TeachingConfig(enabled=True, backend="local", local_path=str(teach))
    ev = research.make_event(session_id="s1", participant_id="", condition="", course_code="", mission="processlab",
                             step="exp1", event_type="result")
    research.LocalBackend(str(teach)).append([teaching.to_teaching_event(ev, "Ada Lovelace", cfg)])
    at = AppTest.from_file(INSTRUCTOR, default_timeout=120)
    at.secrets["instructor_password"] = "pw"
    at.secrets["teaching"] = dict(enabled=True, backend="local", local_path=str(teach))
    at.run()
    at.text_input[0].set_value("pw")
    at.button[0].click().run()
    assert not at.exception
    assert any(m.label == "Students" and m.value == "1" for m in at.metric)
    assert at.dataframe[0].value.loc[0, "student"] == "Ada Lovelace"
