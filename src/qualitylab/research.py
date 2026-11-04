"""Optional, consent-based collection of Learning Lab responses for research.

Nothing is recorded unless *all* of the following hold:

1. the deployment is configured for research (``[research]`` in Streamlit
   secrets, with ``enabled = true``, an IRB protocol number, a secret salt
   and a storage backend), and
2. the student reads the consent information, confirms they are 18 or older
   and chooses to take part.

Students who decline (or deployments without a research configuration) get
exactly the same Learning Lab; their responses stay in their browser session
and can only be downloaded by themselves.

Privacy by design:

* No names, emails, student IDs or IP addresses are collected.
* Participants are identified by a *self-generated identification code*
  (three answers only the student knows, e.g. the first two letters of a
  parent's first name). The answers are combined with a secret salt and
  hashed; only the hash is stored. The same student gets the same code in
  every session, so pre- and post-tests can be linked, but the code cannot be
  traced back to the student by the research team.
* Free-text answers carry a reminder not to include names.

Storage backends:

``local``    a JSON-lines file (for running the app on your own computer)
``webhook``  HTTPS POST to an endpoint you control, e.g. the Google Apps
             Script in ``docs/research/google_apps_script.gs``, which appends
             rows to a Google Sheet, or an equivalent Microsoft Power Automate
             flow. Use whichever platform your IRB approves.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

from . import __version__

FIELDS = ["event_id", "ts_utc", "session_id", "participant_id", "condition", "course_code", "app_version",
          "mission", "step", "event_type", "item_id", "response", "correct", "confidence", "score", "latency_s",
          "detail"]

SGIC_QUESTIONS = (
    ("First two letters of your mother's (or a parent's or guardian's) first name", "e.g. MA", 2, "alpha"),
    ("Day of the month you were born (two digits)", "e.g. 07", 2, "digits"),
    ("First two letters of the town or city where you were born", "e.g. BO", 2, "alpha"),
)


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

@dataclass
class ResearchConfig:
    enabled: bool = False
    study_title: str = ""
    irb_protocol: str = ""
    institution: str = ""
    pi_name: str = ""
    pi_email: str = ""
    irb_contact: str = ""
    course_code: str = ""
    backend: str = "none"
    local_path: str = "research_data/events.jsonl"
    webhook_url: str = ""
    webhook_token: str = ""
    salt: str = ""
    conditions: tuple[str, ...] = ()
    instructor_password: str = ""
    data_access_note: str = ("The instructor may show anonymous, class-level summaries in class (for example, "
                             "“60 % of the class chose the supplier fix”). Nobody will look at individual responses "
                             "until final grades for the course have been submitted, and nobody can tell from the "
                             "data who took part.")
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, m) -> ResearchConfig:
        m = dict(m or {})
        known = {f.name for f in fields(cls)}
        kw = {k: v for k, v in m.items() if k in known}
        if "conditions" in kw:
            kw["conditions"] = tuple(str(c) for c in kw["conditions"])
        if "enabled" in kw:
            kw["enabled"] = str(kw["enabled"]).lower() in ("1", "true", "yes", "on")
        cfg = cls(**kw)
        cfg.extra = {k: v for k, v in m.items() if k not in known}
        return cfg

    def problems(self) -> list[str]:
        p = []
        if not self.enabled:
            return ["research collection is turned off"]
        if not self.irb_protocol.strip():
            p.append("irb_protocol is empty: data may only be collected under an approved IRB protocol")
        if len(self.salt) < 16:
            p.append("salt must be a secret string of at least 16 characters")
        if not self.pi_name.strip() or not self.pi_email.strip():
            p.append("pi_name and pi_email are required (shown to participants)")
        if self.backend == "local":
            pass
        elif self.backend == "webhook":
            if not self.webhook_url.startswith("https://"):
                p.append("webhook_url must be an https:// address")
            if len(self.webhook_token) < 16:
                p.append("webhook_token must be at least 16 characters")
        else:
            p.append("backend must be 'local' or 'webhook'")
        return p

    @property
    def active(self) -> bool:
        return self.enabled and not self.problems()


def load_config(secrets=None) -> ResearchConfig:
    """Read ``[research]`` from Streamlit secrets (or a mapping). Missing → disabled."""
    try:
        if secrets is None:
            import streamlit as st

            secrets = st.secrets
        section = secrets.get("research", {}) if hasattr(secrets, "get") else {}
        return ResearchConfig.from_mapping(section)
    except Exception:  # noqa: BLE001 - no secrets file at all is the normal, disabled case
        return ResearchConfig()


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------

def normalize_sgic(answers) -> tuple[str, ...]:
    out = []
    for (label, _, n, kind), a in zip(SGIC_QUESTIONS, answers):
        a = re.sub(r"[^0-9A-Za-z]", "", str(a or "")).upper()
        if kind == "digits":
            if not a.isdigit() or not 1 <= int(a) <= 31:
                raise ValueError(f"{label}: enter a day between 01 and 31")
            a = f"{int(a):02d}"
        else:
            if len(a) < n or not a[:n].isalpha():
                raise ValueError(f"{label}: enter {n} letters")
            a = a[:n]
        out.append(a)
    return tuple(out)


def participant_id(answers, salt: str) -> str:
    norm = normalize_sgic(answers)
    h = hashlib.sha256(("|".join(norm) + "|" + salt).encode()).hexdigest()
    return "P-" + h[:10].upper()


def assign_condition(pid: str, conditions) -> str:
    conditions = tuple(conditions or ())
    if not conditions:
        return ""
    h = int(hashlib.sha256((pid + "|condition").encode()).hexdigest(), 16)
    return conditions[h % len(conditions)]


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

def make_event(*, session_id: str, participant_id: str, condition: str, course_code: str, mission: str,
               step: str, event_type: str, item_id: str = "", response=None, correct=None, confidence=None,
               score=None, latency_s=None, detail=None) -> dict:
    def j(v):
        return "" if v is None else json.dumps(v, default=_json_default, separators=(",", ":"))

    return {
        "event_id": uuid.uuid4().hex,
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "session_id": session_id,
        "participant_id": participant_id,
        "condition": condition,
        "course_code": course_code,
        "app_version": __version__,
        "mission": mission,
        "step": step,
        "event_type": event_type,
        "item_id": item_id,
        "response": j(response),
        "correct": "" if correct is None else int(bool(correct)),
        "confidence": "" if confidence is None else int(confidence),
        "score": "" if score is None else float(score),
        "latency_s": "" if latency_s is None else round(float(latency_s), 2),
        "detail": j(detail),
    }


def _json_default(o):
    try:
        import numpy as np

        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:  # pragma: no cover
        pass
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


# ---------------------------------------------------------------------------
# backends
# ---------------------------------------------------------------------------

class NullBackend:
    name = "none"

    def append(self, events: list[dict]) -> None:  # noqa: D401
        return None

    def read(self) -> list[dict]:
        return []


class LocalBackend:
    name = "local"
    _lock = threading.Lock()

    def __init__(self, path: str):
        self.path = Path(path)

    def append(self, events: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]


class WebhookBackend:
    """POSTs ``{"token": ..., "events": [...]}``; GET ``?token=...&action=export`` returns ``{"events": [...]}``."""

    name = "webhook"

    def __init__(self, url: str, token: str, timeout: float = 10.0):
        self.url, self.token, self.timeout = url, token, timeout

    def append(self, events: list[dict]) -> None:
        body = json.dumps({"token": self.token, "events": events}).encode()
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "text/plain;charset=utf-8"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310 - https enforced by config
            payload = r.read().decode() or "{}"
        try:
            ok = json.loads(payload).get("ok", True)
        except (json.JSONDecodeError, AttributeError):
            # e.g. a Google sign-in page when the web app is not deployed with access "Anyone"
            raise RuntimeError("the research endpoint did not answer with JSON (check the deployment)") from None
        if not ok:
            raise RuntimeError("the research endpoint rejected the data (check the token)")

    def read(self) -> list[dict]:
        q = urllib.parse.urlencode({"token": self.token, "action": "export"})
        with urllib.request.urlopen(f"{self.url}?{q}", timeout=60) as r:  # noqa: S310
            data = json.loads(r.read().decode())
        if not data.get("ok", True):
            raise RuntimeError("the research endpoint refused the export (check the token)")
        return data.get("events", [])


def make_backend(cfg: ResearchConfig):
    if not cfg.active:
        return NullBackend()
    if cfg.backend == "local":
        return LocalBackend(cfg.local_path)
    return WebhookBackend(cfg.webhook_url, cfg.webhook_token)


class EventSink:
    """Sends events in the background so students never wait on the network.

    Failed batches are kept and retried with the next batch, and again at the end of
    each mission (``flush(wait=False)``). ``flush(wait=True)`` blocks until everything in
    flight is written (used by tests).
    """

    def __init__(self, backend, workers: int = 2):
        self.backend = backend
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="qlab-research")
        self._retry: list[dict] = []
        self._lock = threading.Lock()
        self.failures = 0
        self.sent = 0
        self._futures: set = set()

    def _send(self, events: list[dict]) -> None:
        with self._lock:
            batch = self._retry + events
            self._retry = []
        if not batch:
            return
        try:
            self.backend.append(batch)
            with self._lock:
                self.sent += len(batch)
        except Exception:  # noqa: BLE001 - never break the student's session
            with self._lock:
                self._retry = batch + self._retry
                self.failures += 1

    def submit(self, events: list[dict]):
        if isinstance(self.backend, NullBackend) or not events:
            return None
        return self._track(self._pool.submit(self._send, list(events)))

    def _track(self, fut):
        with self._lock:
            self._futures.add(fut)
        fut.add_done_callback(lambda f: self._discard(f))
        return fut

    def _discard(self, fut) -> None:
        with self._lock:
            self._futures.discard(fut)

    def flush(self, wait: bool = True) -> None:
        """Wait for every batch in flight, then retry anything that failed once more."""
        if wait:
            with self._lock:
                running = list(self._futures)
            for f in running:
                f.result(timeout=60)
        fut = self._track(self._pool.submit(self._send, []))
        if wait:
            fut.result(timeout=60)

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._retry)


_SINKS: dict[str, EventSink] = {}


def get_sink(cfg: ResearchConfig) -> EventSink:
    key = f"{cfg.backend}|{cfg.local_path}|{cfg.webhook_url}|{cfg.active}"
    if key not in _SINKS:
        _SINKS[key] = EventSink(make_backend(cfg))
    return _SINKS[key]

