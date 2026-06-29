"""JSON-backed question store.

Intent:
    Question suites live as JSON under the configured suites dir (one
    <suite>.json per suite) so the management UI can safely read and write them
    (no Python source rewriting). Both the runner and the UI go through here.

A suite is "known" if it has a JSON file in the suites dir or an entry in
quetzal.toml's `[suites]` table. Code roots (the agent's starting hint) come
from the config; a suite may exist as questions-only with no roots.

Assumptions:
    Each data file is a JSON list of objects matching QuestionCase fields.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from quetzal.config import SUITES_DIR
from quetzal.core.storage import validate_path_segment
from quetzal.datasets.services import SERVICE_ROOTS
from quetzal.models import QuestionCase

DATA_DIR = SUITES_DIR


def list_services() -> list[str]:
    """Every known suite: those with a JSON file plus those declared in config."""
    from_files = {p.stem for p in DATA_DIR.glob("*.json")} if DATA_DIR.is_dir() else set()
    return sorted(from_files | set(SERVICE_ROOTS))


def service_hint(service: str) -> str:
    """Code roots for a suite as a bullet list, or a whole-repo hint if none."""
    roots = SERVICE_ROOTS.get(service, ())
    if not roots:
        return "  - (no specific roots configured — explore the whole repository)"
    return "\n".join(f"  - {root}" for root in roots)


def _data_path(service: str) -> Path:
    validate_path_segment(service, "suite")
    return DATA_DIR / f"{service}.json"


def load_cases(service: str) -> list[QuestionCase]:
    path = _data_path(service)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())
    return [_from_row(service, row) for row in rows]


def get_cases(service: str) -> list[QuestionCase]:
    return load_cases(service)


def all_cases() -> list[QuestionCase]:
    cases: list[QuestionCase] = []
    for service in list_services():
        cases.extend(load_cases(service))
    return cases


def save_cases(service: str, cases: list[QuestionCase]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = [{**asdict(case), "tags": list(case.tags)} for case in cases]
    _data_path(service).write_text(json.dumps(rows, indent=2))


def upsert_case(service: str, case: QuestionCase) -> None:
    """Insert or replace a case by id within a suite."""
    cases = load_cases(service)
    by_id = {c.id: c for c in cases}
    by_id[case.id] = case
    save_cases(service, list(by_id.values()))


def delete_case(service: str, case_id: str) -> bool:
    cases = load_cases(service)
    kept = [c for c in cases if c.id != case_id]
    if len(kept) == len(cases):
        return False
    save_cases(service, kept)
    return True


def _from_row(service: str, row: dict) -> QuestionCase:
    return QuestionCase(
        id=row["id"],
        service=row.get("service", service),
        question=row["question"],
        ground_truth=row["ground_truth"],
        difficulty=row.get("difficulty", "medium"),
        tags=tuple(row.get("tags", ())),
        reviewed=bool(row.get("reviewed", False)),
    )
