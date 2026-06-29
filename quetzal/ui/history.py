"""Cross-session score history.

Intent:
    Turn the per-session report files into time-ordered series so the UI can
    chart how each service's accuracy and token cost move across runs.

Outputs:
    Session summaries and per-service history points.
"""

from __future__ import annotations

from dataclasses import dataclass

from quetzal.core.storage import SessionStore
from quetzal.report import build_report


@dataclass
class SessionSummary:
    session_id: str
    started_at: str
    agent_client: str
    agent_model: str
    judge_model: str | None
    services: list[str]
    overall: dict


def _summary(session_id: str) -> SessionSummary | None:
    store = SessionStore(session_id)
    try:
        config = store.load_config()
    except (FileNotFoundError, OSError):
        return None
    report = build_report(session_id)
    return SessionSummary(
        session_id=session_id,
        started_at=config.started_at,
        agent_client=getattr(config, "agent_client", "api"),
        agent_model=config.agent_model,
        judge_model=config.judge_model,
        services=config.services,
        overall=report["overall"],
    )


def list_session_summaries() -> list[dict]:
    """All sessions, newest first, with overall accuracy + token totals."""
    summaries = [s for s in (_summary(sid) for sid in SessionStore.list_sessions()) if s]
    summaries.sort(key=lambda s: s.started_at, reverse=True)
    return [
        {
            "session_id": s.session_id,
            "started_at": s.started_at,
            "agent_client": s.agent_client,
            "agent_model": s.agent_model,
            "judge_model": s.judge_model,
            "services": s.services,
            "overall": s.overall,
        }
        for s in summaries
    ]


def build_history() -> dict:
    """Per-service and overall series, oldest -> newest, for charting."""
    sessions = sorted(
        (s for s in (_summary(sid) for sid in SessionStore.list_sessions()) if s),
        key=lambda s: s.started_at,
    )
    per_service: dict[str, list[dict]] = {}
    overall: list[dict] = []
    for session in sessions:
        report = build_report(session.session_id)
        for service in report["services"]:
            point = {
                "session_id": session.session_id,
                "started_at": session.started_at,
                "agent_model": session.agent_model,
                "accuracy_pct": service["accuracy_pct"],
                "avg_tokens": service["avg_tokens"],
                "judged": service["judged"],
                "correct": service["correct"],
            }
            per_service.setdefault(service["service"], []).append(point)
        overall.append(
            {
                "session_id": session.session_id,
                "started_at": session.started_at,
                "agent_model": session.agent_model,
                "accuracy_pct": session.overall["accuracy_pct"],
                "avg_tokens": session.overall["avg_tokens"],
            }
        )
    return {"per_service": per_service, "overall": overall}
