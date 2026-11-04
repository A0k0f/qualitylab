"""Consent-gated research logging: privacy rules, storage backends, analysis."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest

from qualitylab import research as R
from qualitylab import research_analysis as RA

GOOD = dict(enabled=True, irb_protocol="IRB-1", pi_name="A", pi_email="a@x.edu", backend="local",
            local_path="x.jsonl", salt="s" * 20)


def test_config_is_off_unless_complete():
    assert not R.ResearchConfig().active
    assert not R.load_config({}).active
    assert R.ResearchConfig.from_mapping(GOOD).active
    for k, bad in (("irb_protocol", ""), ("salt", "short"), ("pi_email", ""), ("backend", "s3")):
        cfg = R.ResearchConfig.from_mapping({**GOOD, k: bad})
        assert not cfg.active and cfg.problems()
    w = R.ResearchConfig.from_mapping({**GOOD, "backend": "webhook", "webhook_url": "http://x", "webhook_token": "t"})
    assert len(w.problems()) == 2
    assert R.ResearchConfig.from_mapping({**GOOD, "enabled": "false"}).active is False
    assert isinstance(R.make_backend(R.ResearchConfig()), R.NullBackend)


def test_self_generated_code_is_stable_anonymous_and_salted():
    a = R.participant_id(("Ma", "7", "Bo"), "s" * 20)
    assert a == R.participant_id((" ma ", "07", "BOSTON"), "s" * 20)
    assert a != R.participant_id(("Ma", "7", "Bo"), "t" * 20)
    assert a.startswith("P-") and len(a) == 12 and "MA" not in a[2:]
    for bad in (("M", "07", "BO"), ("MA", "32", "BO"), ("MA", "xx", "BO"), ("12", "07", "BO")):
        with pytest.raises(ValueError):
            R.normalize_sgic(bad)


def test_condition_assignment_is_deterministic_and_balanced():
    conds = ("predict", "no_predict")
    ids = [R.participant_id((a + b, "10", "BO"), "s" * 20) for a in "ABCDEFGHIJKLMNOP" for b in "ABCDEFGHIJ"]
    got = [R.assign_condition(p, conds) for p in ids]
    assert got == [R.assign_condition(p, conds) for p in ids]
    share = got.count("predict") / len(got)
    assert 0.4 < share < 0.6
    assert R.assign_condition("P-X", ()) == ""


def test_event_schema():
    e = R.make_event(session_id="s", participant_id="P-1", condition="c", course_code="X", mission="m", step="s",
                     event_type="answer", response={"a": np.int64(3)}, correct=True, confidence=4, score=np.float64(.5))
    assert list(e) == R.FIELDS
    assert json.loads(e["response"]) == {"a": 3} and e["correct"] == 1 and e["score"] == 0.5


def test_local_backend_roundtrip(tmp_path):
    cfg = R.ResearchConfig.from_mapping({**GOOD, "local_path": str(tmp_path / "d" / "ev.jsonl")})
    sink = R.EventSink(R.make_backend(cfg))
    evs = [R.make_event(session_id="s", participant_id="P-1", condition="", course_code="", mission="m",
                        step=str(i), event_type="x") for i in range(5)]
    sink.submit(evs[:3])
    sink.submit(evs[3:])
    sink.flush()
    assert [e["step"] for e in sorted(R.make_backend(cfg).read(), key=lambda e: e["step"])] == list("01234")


def test_sink_retries_after_failure():
    class Flaky:
        def __init__(self):
            self.calls, self.got = 0, []

        def append(self, events):
            self.calls += 1
            if self.calls == 1:
                raise OSError("network down")
            self.got.extend(events)

    b = Flaky()
    sink = R.EventSink(b, workers=1)
    sink.submit([{"event_id": "1"}]).result()
    assert sink.pending == 1 and sink.failures == 1
    sink.submit([{"event_id": "2"}]).result()
    assert [e["event_id"] for e in b.got] == ["1", "2"] and sink.pending == 0


def test_webhook_backend_against_a_fake_apps_script():
    store, token = [], "t" * 20

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _reply(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if data.get("token") != token:
                return self._reply({"ok": False})
            store.extend(data["events"])
            self._reply({"ok": True, "added": len(data["events"])})

        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if q.get("token", [""])[0] != token:
                return self._reply({"ok": False})
            self._reply({"ok": True, "events": store})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/exec"
    try:
        b = R.WebhookBackend(url, token)
        b.append([{"event_id": "a"}, {"event_id": "b"}])
        assert [e["event_id"] for e in b.read()] == ["a", "b"]
        with pytest.raises(RuntimeError):
            R.WebhookBackend(url, "wrong" * 5).append([{"event_id": "c"}])
        with pytest.raises(RuntimeError):
            R.WebhookBackend(url, "wrong" * 5).read()
    finally:
        srv.shutdown()


def test_analysis_on_synthetic_data():
    ev = RA.synthetic_events(30, seed=2)
    assert {e["course_code"] for e in ev} == {"SYNTHETIC"}
    p = RA.participants(ev)
    assert len(p) == 30
    assert p["pre_score"].between(0, 1).all() and p["post_score"].between(0, 1).all()
    s = RA.summary(p)
    assert s["participants"] == 30 and s["concept"]["n"] == 30
    assert "gain_by_condition" in s
    it = RA.items(ev)
    assert len(it) == 12 and it["pre_n"].eq(30).all()


def test_attempts_are_read_in_order():
    base = dict(session_id="s", participant_id="P-1", condition="", course_code="X", mission="pareto",
                event_type="decision")
    ev = [R.make_event(step="attempt2", score=1.0, **base), R.make_event(step="attempt1", score=0.7, **base)]
    for e in ev:
        e["ts_utc"] = "2026-01-01T00:00:00.000+00:00"
    p = RA.participants(ev)
    assert p.loc["P-1", "pg_first_share_of_optimal"] == pytest.approx(0.7)
    assert p.loc["P-1", "pg_best_share_of_optimal"] == pytest.approx(1.0)


def test_retaken_checks_use_first_pre_and_last_post():
    base = dict(participant_id="P-1", condition="", course_code="X", mission="concept")
    ev = []
    for sess, step, score, item_ok in (("s1", "pre", 0.25, 0), ("s2", "pre", 0.9, 1),
                                       ("s2", "post", 0.5, 0), ("s3", "post", 1.0, 1)):
        ev.append(R.make_event(session_id=sess, step=step, event_type="answer", item_id="C01", correct=item_ok,
                               confidence=1 + 4 * item_ok, **base))
        ev.append(R.make_event(session_id=sess, step=step, event_type="score", score=score, **base))
    p = RA.participants(ev).loc["P-1"]
    assert p["pre_score"] == 0.25 and p["post_score"] == 1.0
    assert p["pre_confidence"] == 1 and p["post_confidence"] == 5
    it = RA.items(ev).loc["C01"]
    assert it["pre_correct"] == 0 and it["post_correct"] == 1


def test_analysis_script_runs(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_learning_lab.py"
    log = tmp_path / "events.jsonl"
    log.write_text("\n".join(json.dumps(e) for e in RA.synthetic_events(12, seed=4)))
    for args in (["--synthetic", "15"], [str(log), "--exclude", "P-SYN00000"]):
        out = tmp_path / ("o" + str(len(args)))
        r = subprocess.run([sys.executable, str(script), *args, "--out", str(out)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        for f in ("participants.csv", "items.csv", "summary.json", "report.md", "calibration.csv"):
            assert (out / f).exists()
    import pandas as pd
    p = pd.read_csv(tmp_path / "o3" / "participants.csv")
    assert len(p) == 11 and "P-SYN00000" not in set(p["participant_id"])
