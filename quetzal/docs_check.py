"""Keep docs fresh — nudge the agent to document a new module.

Intent:
    When a new package/module lands in the repo with no documentation (no
    README in its directory), nudge the developer or agent to write module docs
    *there*. This is the keep-docs-fresh companion installed by `quetzal init`:
    better module docs make a coding-agent harness answer questions about the
    code faster and cheaper — exactly what Quetzal measures.

Design:
    Deliberately high-precision, low-noise. It fires on two unambiguous signals:
      * a *new* package manifest (pyproject.toml, package.json, …; see
        config.MODULE_MANIFESTS) landing in a directory that has no README, and
      * a README *in the current working set* that has grown past a budget that
        scales with its module's size (config.README_BASE_LINES +
        README_LINES_PER_100_LOC per 100 LOC) — a candidate to condense.
    Never on fuzzy "this could use docs" judgments, which would spam the team. It
    self-suppresses when you're already adding docs in that module, and only ever
    looks at files in the working set — never the whole repo.

Usage:
    Wired as a Stop/idle hook per harness (reads the hook payload on stdin and
    prints a harness-native verdict; see --format). Also runnable by hand or
    from a git pre-commit hook — with no stdin it just analyses the working set.

        quetzal docs-check                 # claude-code blocking JSON (default)
        echo '{}' | quetzal docs-check --format codex
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import click

from quetzal.config import (
    MODULE_MANIFESTS,
    README_BASE_LINES,
    README_LINES_PER_100_LOC,
    REPO_ROOT,
)

# Directories that don't count as a module's own code when sizing it.
_LOC_SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
     "target", "vendor", "results", ".mypy_cache", ".pytest_cache", ".next"}
)
# Prose/docs don't count toward "module size" — they're what we're budgeting for.
_LOC_SKIP_SUFFIXES = frozenset({".md", ".rst", ".txt"})


def _read_payload() -> dict:
    """The hook payload arrives on stdin; absent when run by hand."""
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _changed_paths(repo: Path) -> tuple[list[Path], list[Path]]:
    """(added, all_changed) repo-relative paths from `git status`.

    `added` = newly tracked or untracked files (the only place a *new* manifest
    can appear); `all_changed` includes modifications, used to self-suppress.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return [], []
    if out.returncode != 0:
        return [], []

    added: list[Path] = []
    changed: list[Path] = []
    for line in out.stdout.splitlines():
        if len(line) < 4:
            continue
        index, worktree, rest = line[0], line[1], line[3:]
        # Renames show as "old -> new"; the new path is what matters.
        rel = rest.split(" -> ", 1)[-1].strip().strip('"')
        path = Path(rel)
        changed.append(path)
        if index == "A" or "?" in (index + worktree):
            added.append(path)
    return added, changed


def _is_doc(path: Path) -> bool:
    """A README (any extension) or anything under a module's docs/ directory."""
    return path.name.lower().startswith("readme") or "docs" in path.parts


def _has_docs(module_dir: Path) -> bool:
    """True if the module directory already carries documentation."""
    if not module_dir.is_dir():
        return False
    if (module_dir / "docs").is_dir():
        return True
    return any(p.is_file() and p.name.lower().startswith("readme") for p in module_dir.iterdir())


def find_undocumented_modules() -> list[str]:
    """Directories of newly added manifests that have no docs (the nudge set)."""
    repo = REPO_ROOT
    added, changed = _changed_paths(repo)
    if not added:
        return []

    # If the working set already adds docs under a module dir, that module is
    # being handled — suppress it.
    documenting = {
        str((repo / p).resolve().parent) for p in changed if _is_doc(p)
    }

    undocumented: list[str] = []
    seen: set[str] = set()
    for path in added:
        if path.name not in MODULE_MANIFESTS:
            continue
        module_dir = path.parent
        key = str(module_dir)
        if key in seen:
            continue
        seen.add(key)
        module_abs = (repo / module_dir).resolve()
        if str(module_abs) in documenting:
            continue
        if not _has_docs(module_abs):
            undocumented.append(key or ".")
    return undocumented


def _module_loc(module_dir: Path) -> int:
    """Lines of code under a module dir (excludes prose, vendored/build dirs).

    Caps out early — past the cap the budget is already generous, so there's no
    point walking a huge tree exactly.
    """
    total = 0
    for p in module_dir.rglob("*"):
        if not p.is_file() or p.suffix.lower() in _LOC_SKIP_SUFFIXES:
            continue
        if any(part in _LOC_SKIP_DIRS for part in p.relative_to(module_dir).parts):
            continue
        try:
            total += len(p.read_text().splitlines())
        except (OSError, UnicodeDecodeError):
            continue
        if total > 200_000:
            break
    return total


def _readme_budget(module_loc: int) -> int:
    """Allowed README length for a module of this size."""
    return README_BASE_LINES + (README_LINES_PER_100_LOC * module_loc) // 100


def find_bloated_readmes() -> list[tuple[str, int, int]]:
    """Changed READMEs over their size-relative budget — candidates to condense.

    Returns (path, lines, budget). Only looks at READMEs in the working set
    (added or modified), so it nudges about docs you're actually touching, never
    the whole repo. Disabled when both budget knobs are 0.
    """
    if README_BASE_LINES <= 0 and README_LINES_PER_100_LOC <= 0:
        return []
    repo = REPO_ROOT
    _, changed = _changed_paths(repo)
    bloated: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for path in changed:
        if not path.name.lower().startswith("readme"):
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        f = repo / path
        if not f.is_file():
            continue
        try:
            lines = len(f.read_text().splitlines())
        except (OSError, UnicodeDecodeError):
            continue
        budget = _readme_budget(_module_loc(f.parent))
        if lines > budget:
            bloated.append((key, lines, budget))
    return bloated


def _reason(undocumented: list[str], bloated: list[tuple[str, int, int]], with_skill: bool = False) -> str:
    parts: list[str] = []
    if undocumented:
        how = "use the `document-module` skill to write" if with_skill else "write"
        parts.append(
            f"a new module landed ({', '.join(undocumented)}) with no documentation — {how} a README "
            "in that directory (purpose, public API/usage, key files, how it fits) derived from the code"
        )
    if bloated:
        listed = ", ".join(f"{p} ({n} lines vs ~{b} expected for a module this size)" for p, n, b in bloated)
        parts.append(
            f"the README {listed} has grown long for its module — condense it: cut redundancy, move "
            "deep detail elsewhere, and keep purpose, API, and key files"
        )
    return f"Quetzal: {'; also '.join(parts)}. Or stop if this isn't warranted."


@click.command()
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["claude-code", "codex", "cursor", "git", "json"]),
    default="claude-code",
    help="How to emit the nudge — matched to the harness whose hook calls this.",
)
def main(fmt: str) -> None:
    """Nudge to document a new module — or to condense a README that's grown bloated.

    Output per --format (only emitted when a nudge is actually due):
      claude-code  blocking decision JSON on stdout (Claude Code Stop hook)
      codex        reason on stderr, exit 2  (Codex Stop hook blocks on exit 2)
      cursor       {"continue": true, "followup_message": ...} on stdout (Cursor `stop` hook)
      git          reason on stderr, exit 1  (git pre-commit: warn, don't block)
      json         {"nudge": bool, "undocumented": [...], "bloated": [[path, lines], ...],
                   "reason": ...} on stdout, exit 0 (programmatic callers, e.g. an opencode plugin)
    """
    payload = _read_payload()
    # Claude Code / Codex re-fire the Stop hook after a block; bail so we never loop.
    if payload.get("stop_hook_active"):
        return

    undocumented = find_undocumented_modules()
    bloated = find_bloated_readmes()
    if not undocumented and not bloated:
        if fmt == "json":
            click.echo(json.dumps({"nudge": False, "undocumented": [], "bloated": []}))
        return

    reason = _reason(undocumented, bloated, with_skill=(fmt == "claude-code"))
    if fmt == "claude-code":
        # Claude Code Stop-hook contract: blocking decision + reason fed to the agent.
        click.echo(json.dumps({"decision": "block", "reason": reason}))
    elif fmt == "codex":
        # Codex Stop-hook contract: exit 2 blocks the stop; stderr is fed back.
        click.echo(reason, err=True)
        sys.exit(2)
    elif fmt == "cursor":
        # Cursor `stop` hook: auto-submit a follow-up to keep the agent iterating.
        click.echo(json.dumps({"continue": True, "followup_message": reason}))
    elif fmt == "json":
        click.echo(json.dumps({"nudge": True, "undocumented": undocumented, "bloated": bloated, "reason": reason}))
    else:  # git pre-commit: warn without blocking the commit
        click.echo(reason, err=True)
        sys.exit(1)
