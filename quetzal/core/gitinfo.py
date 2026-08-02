"""Best-effort git state of the repository under test."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitState:
    commit: str | None
    branch: str | None
    dirty: bool


def _git(repo_root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, timeout=5)
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:  # noqa: BLE001 - provenance is best-effort metadata
        return ""


def git_state(repo_root: Path) -> GitState:
    return GitState(
        commit=_git(repo_root, "rev-parse", "HEAD") or None,
        branch=_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD") or None,
        dirty=bool(_git(repo_root, "status", "--porcelain")),
    )
