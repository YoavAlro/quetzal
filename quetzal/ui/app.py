"""FastAPI app powering the local management UI.

Intent:
    Serve a build-free local frontend plus a small JSON API to manage
    question suites (CRUD against the JSON store) and to read score history from
    past benchmark sessions.

Assumptions:
    Runs locally for a single developer; no auth. Never expose publicly.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from quetzal.core.storage import validate_path_segment
from quetzal.datasets import (
    SERVICE_ROOTS,
    delete_case,
    list_services,
    load_cases,
    upsert_case,
)
from quetzal.models import QuestionCase
from quetzal.report import build_report
from quetzal.ui.history import build_history, list_session_summaries

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Quetzal — Console", docs_url="/api/docs")


class QuestionPayload(BaseModel):
    id: str | None = Field(default=None, description="Stable slug; auto-generated if omitted.")
    question: str
    ground_truth: str
    difficulty: str = "medium"
    tags: list[str] = Field(default_factory=list)


def _slugify(service: str, question: str, existing: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", f"{service}_{question.lower()}").strip("_")[:48] or service
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _require_service(service: str) -> None:
    if service not in set(list_services()):
        raise HTTPException(status_code=404, detail=f"Unknown service '{service}'.")


def _case_dict(case: QuestionCase) -> dict:
    return {
        "id": case.id,
        "service": case.service,
        "question": case.question,
        "ground_truth": case.ground_truth,
        "difficulty": case.difficulty,
        "tags": list(case.tags),
    }


@app.get("/api/services")
def get_services() -> list[dict]:
    """Service suites with question counts and their latest benchmark score."""
    history = build_history()["per_service"]
    out = []
    for service in list_services():
        cases = load_cases(service)
        by_difficulty: dict[str, int] = {}
        for case in cases:
            by_difficulty[case.difficulty] = by_difficulty.get(case.difficulty, 0) + 1
        points = history.get(service, [])
        latest = points[-1] if points else None
        out.append(
            {
                "name": service,
                "code_roots": list(SERVICE_ROOTS.get(service, ())),
                "total": len(cases),
                "latest_score": latest["accuracy_pct"] if latest else None,
                "latest_session": latest["session_id"] if latest else None,
                "latest_at": latest["started_at"] if latest else None,
                "by_difficulty": by_difficulty,
            }
        )
    return out


@app.get("/api/services/{service}/questions")
def get_questions(service: str) -> list[dict]:
    _require_service(service)
    return [_case_dict(c) for c in load_cases(service)]


@app.post("/api/services/{service}/questions")
def create_question(service: str, payload: QuestionPayload) -> dict:
    _require_service(service)
    existing = {c.id for c in load_cases(service)}
    case_id = (payload.id or "").strip() or _slugify(service, payload.question, existing)
    try:
        validate_path_segment(case_id, "question id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if case_id in existing:
        raise HTTPException(status_code=409, detail=f"Question id '{case_id}' already exists.")
    case = QuestionCase(
        id=case_id,
        service=service,
        question=payload.question,
        ground_truth=payload.ground_truth,
        difficulty=payload.difficulty,
        tags=tuple(payload.tags),
    )
    upsert_case(service, case)
    return _case_dict(case)


@app.put("/api/services/{service}/questions/{case_id}")
def update_question(service: str, case_id: str, payload: QuestionPayload) -> dict:
    _require_service(service)
    if case_id not in {c.id for c in load_cases(service)}:
        raise HTTPException(status_code=404, detail=f"Question '{case_id}' not found.")
    case = QuestionCase(
        id=case_id,
        service=service,
        question=payload.question,
        ground_truth=payload.ground_truth,
        difficulty=payload.difficulty,
        tags=tuple(payload.tags),
    )
    upsert_case(service, case)
    return _case_dict(case)


@app.delete("/api/services/{service}/questions/{case_id}")
def remove_question(service: str, case_id: str) -> dict:
    _require_service(service)
    if not delete_case(service, case_id):
        raise HTTPException(status_code=404, detail=f"Question '{case_id}' not found.")
    return {"deleted": case_id}


@app.get("/api/sessions")
def get_sessions() -> list[dict]:
    return list_session_summaries()


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        return build_report(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.") from exc


@app.get("/api/history")
def get_history() -> dict:
    return build_history()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
