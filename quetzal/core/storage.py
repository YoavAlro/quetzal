"""JSON persistence for benchmark sessions.

Intent:
    Each pipeline step reads and writes the same on-disk session so steps stay
    decoupled. One file per case keeps re-runs and re-scoring incremental.

Layout:
    results/<session_id>/config.json
    results/<session_id>/<service>/<case_id>.json
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from quetzal.config import RESULTS_DIR
from quetzal.models import CaseResult, SessionConfig


class SessionNotFoundError(FileNotFoundError):
    """Raised when a session id has no results directory on disk."""


def validate_path_segment(value: str, kind: str) -> str:
    """Ensure a value is a single path segment, so it can never escape its parent
    dir when joined (guards reset()/save_result against '..', '/', '\\', absolutes)."""
    if not value or value in {".", ".."} or "/" in value or "\\" in value or value != Path(value).name:
        raise ValueError(f"Invalid {kind} {value!r}: must be a single path segment (no '/', '\\', or '..').")
    return value


class SessionStore:
    """Reads/writes one benchmark session under results/."""

    def __init__(self, session_id: str):
        # reset() runs shutil.rmtree on self.root, so the id must never escape RESULTS_DIR.
        self.session_id = validate_path_segment(session_id, "session id")
        self.root = RESULTS_DIR / session_id

    def exists(self) -> bool:
        return self.root.is_dir()

    def reset(self) -> None:
        """Clear any prior results for this session. One run owns its session, so a
        re-run (or a `--limit` subset) never mixes with leftover files from before."""
        if self.root.exists():
            shutil.rmtree(self.root)

    def save_config(self, config: SessionConfig) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._write(self.root / "config.json", asdict(config))

    def load_config(self) -> SessionConfig:
        data = json.loads((self.root / "config.json").read_text())
        return SessionConfig(**data)

    def save_result(self, result: CaseResult) -> None:
        # Guard against a crafted service/id escaping the session dir (e.g. overwriting config.json).
        service = validate_path_segment(result.case.service, "service")
        case_id = validate_path_segment(result.case.id, "question id")
        service_dir = self.root / service
        service_dir.mkdir(parents=True, exist_ok=True)
        self._write(service_dir / f"{case_id}.json", result.to_dict())

    def load_results(self, service: str | None = None) -> list[CaseResult]:
        if not self.root.is_dir():
            raise SessionNotFoundError(f"Session '{self.session_id}' not found at {self.root}")
        results: list[CaseResult] = []
        for service_dir in sorted(self.root.iterdir()):
            if not service_dir.is_dir() or (service and service_dir.name != service):
                continue
            for case_file in sorted(service_dir.glob("*.json")):
                results.append(CaseResult.from_dict(json.loads(case_file.read_text())))
        return results

    @staticmethod
    def list_sessions() -> list[str]:
        if not RESULTS_DIR.is_dir():
            return []
        return sorted(p.name for p in RESULTS_DIR.iterdir() if (p / "config.json").exists())

    @staticmethod
    def _write(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2, default=str))
