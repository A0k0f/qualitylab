"""Optional participation record for the Learning Lab (teaching use, not research).

When the deployment has a complete ``[teaching]`` section in its secrets, students
type their name before using the Learning Lab and their activity is sent to a store
the instructor controls (for example a Google Sheet in the university account), so the
instructor can see who took part and what they did.

This is kept strictly apart from the research data:

* teaching records carry the student's **name** and never the anonymous research code
  or the experimental condition;
* research records carry the anonymous code and never the name;
* the two go to different stores with different tokens.

``detail = "full"`` keeps every input (settings, predictions, answers, notes);
``detail = "summary"`` keeps only what is needed to check participation (what was
started and finished, and when). Use ``summary`` while a research study is running,
so that the participation record cannot be used to identify research participants.
"""
from __future__ import annotations

from dataclasses import dataclass, fields

import pandas as pd

from .research import EventSink, LocalBackend, NullBackend, WebhookBackend

FIELDS = ["event_id", "ts_utc", "session_id", "student", "course_code", "app_version", "mission", "step",
          "event_type", "item_id", "response", "correct", "score", "latency_s", "detail"]
SUMMARY_KEEP = ("event_id", "ts_utc", "session_id", "student", "course_code", "app_version", "mission", "step",
                "event_type", "latency_s")


@dataclass
class TeachingConfig:
    enabled: bool = False
    course_code: str = ""
    backend: str = "webhook"
    webhook_url: str = ""
    webhook_token: str = ""
    local_path: str = "teaching_data/participation.jsonl"
    detail: str = "full"

    @classmethod
    def from_mapping(cls, m) -> TeachingConfig:
        m = dict(m or {})
        known = {f.name for f in fields(cls)}
        kw = {k: v for k, v in m.items() if k in known}
        if "enabled" in kw:
            kw["enabled"] = str(kw["enabled"]).lower() in ("1", "true", "yes", "on")
        return cls(**kw)

    def problems(self) -> list[str]:
        if not self.enabled:
            return ["participation record is turned off"]
        p = []
        if self.backend == "webhook":
            if not self.webhook_url.startswith("https://"):
                p.append("webhook_url must be an https:// address")
            if len(self.webhook_token) < 16:
                p.append("webhook_token must be at least 16 characters")
        elif self.backend != "local":
            p.append("backend must be 'webhook' or 'local'")
        if self.detail not in ("full", "summary"):
            p.append("detail must be 'full' or 'summary'")
        return p

    @property
    def active(self) -> bool:
        return self.enabled and not self.problems()


def load_config(secrets=None) -> TeachingConfig:
    try:
        if secrets is None:
            import streamlit as st

            secrets = st.secrets
        return TeachingConfig.from_mapping(secrets.get("teaching", {}) if hasattr(secrets, "get") else {})
    except Exception:  # noqa: BLE001 - no secrets at all: off
        return TeachingConfig()


def make_backend(cfg: TeachingConfig):
    if not cfg.active:
        return NullBackend()
    if cfg.backend == "local":
        return LocalBackend(cfg.local_path)
    return WebhookBackend(cfg.webhook_url, cfg.webhook_token, fields=FIELDS)


_SINKS: dict[str, EventSink] = {}


def get_sink(cfg: TeachingConfig) -> EventSink:
    key = f"{cfg.backend}|{cfg.local_path}|{cfg.webhook_url}|{cfg.active}"
    if key not in _SINKS:
        _SINKS[key] = EventSink(make_backend(cfg))
    return _SINKS[key]


def clean_name(name: str) -> str:
    name = " ".join(str(name or "").split())
    if not 2 <= len(name) <= 60:
        raise ValueError("Please enter your name (2 to 60 characters).")
    return name


def to_teaching_event(ev: dict, student: str, cfg: TeachingConfig) -> dict:
    """A Learning Lab event, re-labelled with the student's name. Drops the research code and condition."""
    out = {k: ev.get(k, "") for k in FIELDS if k != "student"}
    out["student"] = student
    out["course_code"] = cfg.course_code
    if cfg.detail == "summary":
        out = {k: (out[k] if k in SUMMARY_KEEP else "") for k in FIELDS}
    return {k: out.get(k, "") for k in FIELDS}


# ---------------------------------------------------------------------------
# instructor view
# ---------------------------------------------------------------------------

def participation(events) -> pd.DataFrame:
    """One row per student: when they worked, and what they started and finished."""
    df = pd.DataFrame(list(events))
    if df.empty:
        return pd.DataFrame()
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], errors="coerce", utc=True)
    df["key"] = df["student"].astype(str).str.strip().str.lower()
    df = df.drop_duplicates("event_id").sort_values("ts_utc")
    rows = []
    for _, g in df.groupby("key"):
        sessions = g.groupby("session_id")["ts_utc"].agg(["min", "max"])
        active = float(((sessions["max"] - sessions["min"]).dt.total_seconds() / 60).sum())
        done = set(g.loc[g["event_type"] == "complete", "mission"])
        exp_runs = g[(g["mission"] == "processlab") & (g["event_type"] == "result")]
        rows.append(dict(
            student=g["student"].iloc[-1], course_code=g["course_code"].iloc[-1], sessions=len(sessions),
            first_seen=g["ts_utc"].min(), last_seen=g["ts_utc"].max(), minutes_active=round(active, 1),
            warm_up_check=bool(((g["mission"] == "concept") & (g["step"] == "pre") & (g["event_type"] == "score")).any()),
            process_lab_experiments=int(len(exp_runs)), process_lab_finished="processlab" in done,
            missions_finished=int(len(done - {"processlab", "survey"})),
            final_check=bool(((g["mission"] == "concept") & (g["step"] == "post") & (g["event_type"] == "score")).any()),
            feedback="survey" in done,
            notes=int(((g["event_type"] == "text") & (g["mission"] == "processlab")).sum()),
        ))
    out = pd.DataFrame(rows).sort_values("student", key=lambda s: s.str.lower()).reset_index(drop=True)
    for c in ("first_seen", "last_seen"):
        out[c] = out[c].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d %H:%M")
    return out
