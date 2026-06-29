"""Shared paths and tunables, resolved from a quetzal.toml config.

Quetzal evaluates a coding-agent harness against questions about a *target
codebase*. The target repo, the suites (named code areas) and where results
land are read from a `quetzal.toml` discovered by walking up from the current
directory (or pointed at by `QUETZAL_CONFIG`). Every value is overridable by
env var so CI and ad-hoc runs need no file.

Resolution order for each setting: env var > quetzal.toml > built-in default.
Relative paths in the config resolve against the config file's directory.

Outputs:
    REPO_ROOT, SUITES_DIR, RESULTS_DIR, SUITE_ROOTS, and agent defaults.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Final


def _find_config() -> Path | None:
    explicit = os.environ.get("QUETZAL_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()
    for parent in (Path.cwd(), *Path.cwd().parents):
        candidate = parent / "quetzal.toml"
        if candidate.is_file():
            return candidate
    return None


_CONFIG_PATH: Final[Path | None] = _find_config()
_CONFIG: dict = tomllib.loads(_CONFIG_PATH.read_text()) if _CONFIG_PATH else {}
_BASE: Final[Path] = _CONFIG_PATH.parent if _CONFIG_PATH else Path.cwd()


def _resolve(value: str | None, default: Path) -> Path:
    """Resolve a configured path against the config dir; fall back to default."""
    if not value:
        return default.resolve()
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (_BASE / path).resolve()


# The codebase under test — what the answerer agent explores.
REPO_ROOT: Final[Path] = _resolve(
    os.environ.get("QUETZAL_TARGET_REPO") or _CONFIG.get("target_repo"), _BASE
)

# Where question suites (one <suite>.json per file) live.
SUITES_DIR: Final[Path] = _resolve(
    os.environ.get("QUETZAL_SUITES_DIR") or _CONFIG.get("suites_dir"), _BASE / "suites"
)

# Where benchmark sessions are written.
RESULTS_DIR: Final[Path] = _resolve(
    os.environ.get("QUETZAL_RESULTS_DIR") or _CONFIG.get("results_dir"), _BASE / "results"
)

# suite name -> code root(s) relative to REPO_ROOT, handed to the agent as a hint.
SUITE_ROOTS: Final[dict[str, tuple[str, ...]]] = {
    name: tuple(roots) for name, roots in (_CONFIG.get("suites") or {}).items()
}

# Answerer agent
DEFAULT_AGENT: Final[str] = "claude-code"
DEFAULT_AGENT_MODEL: Final[str | None] = None  # None = let the agent CLI use its default model
AGENT_TIMEOUT_S: Final[int] = 600  # per-question wall-clock cap for a CLI run

# Read-only tool allowlist for the Claude Code client (no edits, no shell writes).
CLAUDE_ALLOWED_TOOLS: Final[tuple[str, ...]] = ("Read", "Grep", "Glob", "LS")
