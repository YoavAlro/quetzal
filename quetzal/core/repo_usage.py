"""Inventory repository context assets and observe their use in harness events.

The inventory is deterministic. Usage is intentionally best-effort: a resource
is counted only when its path appears inside a structured tool/command event
emitted by the harness. Some CLIs hide internal reads and hook execution.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from quetzal.config import IGNORED_DIRS
from quetzal.models import RepoResources

_TOOL_TYPES = {
    "command_execution",
    "function_call",
    "hook",
    "mcp_tool_call",
    "tool",
    "tool-call",
    "tool_call",
    "tool_use",
}


@lru_cache(maxsize=8)
def inventory_repo(repo_root: Path) -> RepoResources:
    repo_root = repo_root.resolve()
    markdown: list[str] = []
    skills: list[str] = []
    hooks: list[str] = []
    for current, dirs, files in os.walk(repo_root):
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
        base = Path(current)
        for filename in files:
            path = base / filename
            relative = path.relative_to(repo_root)
            name = filename.lower()
            rel = relative.as_posix()
            if name.endswith(".md"):
                markdown.append(rel)
            if name == "skill.md" and any(part.lower() == "skills" for part in relative.parts):
                skills.append(rel)
            if _is_hook(relative) or _declares_hooks(path, relative):
                hooks.append(rel)
    return RepoResources(
        markdown_files=tuple(sorted(markdown)),
        skill_files=tuple(sorted(skills)),
        hook_files=tuple(sorted(hooks)),
    )


def _is_hook(path: Path) -> bool:
    parts = tuple(part.lower() for part in path.parts)
    name = path.name.lower()
    return (
        "hooks" in parts
        or ".githooks" in parts
        or ".husky" in parts
        or name
        in {
            ".pre-commit-config.yaml",
            ".pre-commit-config.yml",
            "hooks.json",
            "hooks.yaml",
            "hooks.yml",
            "lefthook.yaml",
            "lefthook.yml",
        }
        or ("plugin" in parts and any(part in {".opencode", ".claude", ".codex", ".cursor"} for part in parts))
    )


def _declares_hooks(path: Path, relative: Path) -> bool:
    """Count agent settings files that define hooks inline."""
    if path.name.lower() not in {"settings.json", "settings.local.json"}:
        return False
    if not any(part.lower() in {".claude", ".codex", ".cursor"} for part in relative.parts):
        return False
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and bool(data.get("hooks"))


class RepoUsageCollector:
    """Collect unique inventory paths mentioned by structured tool events."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.inventory = inventory_repo(repo_root)
        self._markdown: set[str] = set()
        self._skills: set[str] = set()
        self._hooks: set[str] = set()

    def observe_event(self, event: Any) -> None:
        for payload in _tool_payloads(event):
            text = _tool_input_text(payload)
            self._match(text, self.inventory.markdown_files, self._markdown)
            self._match(text, self.inventory.skill_files, self._skills)
            self._match(text, self.inventory.hook_files, self._hooks)

    def result(self) -> RepoResources:
        return RepoResources(
            markdown_files=tuple(sorted(self._markdown)),
            skill_files=tuple(sorted(self._skills)),
            hook_files=tuple(sorted(self._hooks)),
            trace_available=True,
        )

    def _match(self, text: str, candidates: tuple[str, ...], found: set[str]) -> None:
        normalized = text.replace("\\\\", "/")
        for relative in candidates:
            absolute = (self.repo_root / relative).as_posix()
            if relative in normalized or absolute in normalized:
                found.add(relative)


def _tool_payloads(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            found.extend(_tool_payloads(item))
        return found
    if not isinstance(value, dict):
        return found

    kind = str(value.get("type", "")).lower().replace(" ", "_")
    if kind in _TOOL_TYPES or "tool_use" in kind or "command_execution" in kind:
        found.append(value)
        return found
    for child in value.values():
        found.extend(_tool_payloads(child))
    return found


def _tool_input_text(payload: dict[str, Any]) -> str:
    """Serialize only invocation inputs, never tool output or result text."""
    inputs: list[Any] = []
    for key in ("input", "arguments", "args", "command", "path", "file_path", "pattern"):
        if key in payload:
            inputs.append(payload[key])
    state = payload.get("state")
    if isinstance(state, dict):
        for key in ("input", "arguments", "args", "command", "path", "file_path"):
            if key in state:
                inputs.append(state[key])
    return json.dumps(inputs, default=str)
