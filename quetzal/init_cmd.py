"""`quetzal init` — set Quetzal up against a target repo in one step.

Run from inside the codebase you want to benchmark, it:

  * writes a `quetzal.toml` (target_repo = ".", empty [suites] to fill in),
  * creates `suites/` and `results/`,
  * installs a *keep-docs-fresh* hook **native to your chosen agent harness**
    so a new module without a README nudges the agent to document it,
  * (optionally) installs a harness-agnostic git pre-commit hook too,
  * reports which answerer CLIs are installed.

The harness is chosen with `--agent`; if omitted, `init` asks. Each harness gets
its own native integration (Claude Code / Codex Stop hooks, a Cursor `stop`
hook, or an opencode plugin), all powered by the shared `quetzal docs-check`.

Everything is idempotent: existing files are left alone unless `--force`, and
hooks are merged into existing config rather than clobbering it.
"""

from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path

import click

AGENTS = ("claude-code", "codex", "cursor", "opencode")

# README condense budget presets -> (base lines, extra lines per 100 LOC).
# The budget scales with module size; bigger modules earn longer READMEs.
README_PRESETS = {
    "concise": (25, 10),
    "balanced": (40, 20),
    "thorough": (70, 35),
}

QUETZAL_TOML_TEMPLATE = '''\
# Quetzal configuration. Quetzal evaluates a coding-agent harness by having it
# answer questions about this codebase, then judging the answers against ground
# truth. Every value is overridable by env var (QUETZAL_TARGET_REPO,
# QUETZAL_SUITES_DIR, QUETZAL_RESULTS_DIR, QUETZAL_CONFIG).

target_repo  = "."        # the codebase under test (relative to this file)
suites_dir   = "suites"   # one <suite>.json question file per suite
results_dir  = "results"  # benchmark sessions are written here

# suite name -> code root(s) relative to target_repo (the agent's starting hint).
# Add an entry per code area you want to benchmark, e.g.:
#   auth    = ["services/auth"]
#   billing = ["services/billing", "libs/money"]
[suites]
'''

GIT_PRECOMMIT_TEMPLATE = '''\
#!/usr/bin/env bash
# Quetzal docs reminder — git pre-commit hook (installed by `quetzal init
# --git-hook`). Harness-agnostic. Warns (does not block) when a new, undocumented
# module is about to be committed.
QUETZAL_BIN="{quetzal_bin}"
command -v "$QUETZAL_BIN" >/dev/null 2>&1 || QUETZAL_BIN="quetzal"
"$QUETZAL_BIN" docs-check --format git || true
'''

OPENCODE_PLUGIN_TEMPLATE = '''\
// Quetzal docs reminder — opencode plugin (installed by `quetzal init`).
// On session idle it asks `quetzal docs-check` whether a new module landed
// with no README and surfaces a nudge. Notify-only (non-blocking).
const QUETZAL_BIN = "{quetzal_bin}";

export const QuetzalDocsReminder = async ({{ $, client }}) => {{
  return {{
    event: async ({{ event }}) => {{
      if (event.type !== "session.idle") return;
      let out = "";
      try {{
        const res = await $`${{QUETZAL_BIN}} docs-check --format json`.quiet().nothrow();
        out = res.stdout.toString().trim();
      }} catch {{
        return;
      }}
      let data;
      try {{
        data = JSON.parse(out || "{{}}");
      }} catch {{
        return;
      }}
      if (!data.nudge) return;
      // Best-effort surfacing; exact client API is opencode-version-dependent.
      try {{
        await client.tui.showToast({{ body: {{ message: data.reason, variant: "warning" }} }});
      }} catch {{
        console.error(data.reason);
      }}
    }},
  }};
}};
'''

SKILL_TEMPLATE = '''\
---
name: document-module
description: >-
  Write or update documentation for a code module/package in this repo. Use
  when a new library/service lands, when asked to document a module, or when
  the keep-docs-fresh reminder hook fires.
---

# Document a module

When a new module lands, add documentation **in that module's directory** so the
codebase — and any coding agent answering questions about it — can navigate it.
Good module docs are what Quetzal's benchmark rewards: they make the agent answer
faster and cheaper.

## Steps

1. **Read the module first.** Open its entry points and public API; understand
   what it does and how it's used elsewhere. Document only what the code shows —
   don't invent behavior.

2. **Add a `README.md` in the module directory** covering:
   - **Purpose** — what the module does and why it exists.
   - **Public API / usage** — the entry points a caller uses, with a short example.
   - **Key files** — where the important pieces live.
   - **How it fits** — its role in the wider repo and notable dependencies.
   - **Gotchas** — anything non-obvious or easy to get wrong.

3. **Expand docstrings** on the module's public functions/classes where they're
   thin, so the docs and the code agree.

4. **Keep it tight and current** — short and accurate beats long and stale.
'''


# --- small filesystem helpers ------------------------------------------------

def _write_if_absent(path: Path, content: str, force: bool, label: str) -> bool:
    if path.exists() and not force:
        click.echo(f"  • {label}: exists, left as-is ({path})")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    click.echo(f"  ✓ {label}: {path}")
    return True


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _docs_check_block(preset: str) -> str:
    base, per100 = README_PRESETS[preset]
    return (
        "\n[docs_check]\n"
        "# README condense budget scales with module size:\n"
        "#   allowed lines = readme_base_lines + readme_lines_per_100_loc * (module LOC / 100)\n"
        f"# chosen detail: {preset}\n"
        f"readme_base_lines        = {base}\n"
        f"readme_lines_per_100_loc = {per100}\n"
    )


def _hook_script(quetzal_bin: str, fmt: str) -> str:
    return (
        "#!/usr/bin/env bash\n"
        "# Quetzal docs reminder — installed by `quetzal init`. Nudges the agent to\n"
        "# document a module when a new package lands with no README.\n"
        "set -euo pipefail\n"
        f'QUETZAL_BIN="{quetzal_bin}"\n'
        'command -v "$QUETZAL_BIN" >/dev/null 2>&1 || QUETZAL_BIN="quetzal"\n'
        f'exec "$QUETZAL_BIN" docs-check --format {fmt}\n'
    )


def _write_hook_script(path: Path, quetzal_bin: str, fmt: str, force: bool, label: str) -> None:
    if _write_if_absent(path, _hook_script(quetzal_bin, fmt), force, label):
        _make_executable(path)


def _merge_nested_stop_hook(json_path: Path, command: str, marker: str) -> None:
    """Merge a Claude-Code/Codex-shaped Stop hook into a JSON config in place.

    Both use `hooks.Stop[].hooks[] = {type: command, command}`. Idempotent:
    skips if a hook command already ends with `marker`.
    """
    data: dict = {}
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text())
        except json.JSONDecodeError:
            click.echo(f"  • {json_path.name} isn't valid JSON, skipping merge ({json_path})")
            return
    stop = data.setdefault("hooks", {}).setdefault("Stop", [])
    if any(
        h.get("command", "").endswith(marker)
        for group in stop
        if isinstance(group, dict)
        for h in group.get("hooks", [])
    ):
        click.echo(f"  • Stop hook: already registered in {json_path.name}")
        return
    stop.append({"hooks": [{"type": "command", "command": command}]})
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2) + "\n")
    click.echo(f"  ✓ Stop hook registered in {json_path}")


def _merge_cursor_hook(json_path: Path, command: str, marker: str) -> None:
    """Merge a Cursor `stop` hook into `.cursor/hooks.json` in place."""
    data: dict = {"version": 1}
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text())
        except json.JSONDecodeError:
            click.echo(f"  • hooks.json isn't valid JSON, skipping merge ({json_path})")
            return
    data.setdefault("version", 1)
    stop = data.setdefault("hooks", {}).setdefault("stop", [])
    if any(isinstance(h, dict) and h.get("command", "").endswith(marker) for h in stop):
        click.echo("  • stop hook: already registered in hooks.json")
        return
    stop.append({"command": command, "loop_limit": 10})
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2) + "\n")
    click.echo(f"  ✓ stop hook registered in {json_path}")


def _ensure_gitignore(repo: Path, results_dirname: str) -> None:
    gitignore = repo / ".gitignore"
    entry = f"{results_dirname}/"
    existing = gitignore.read_text() if gitignore.exists() else ""
    if entry in existing.split():
        return
    prefix = "" if existing.endswith("\n") or not existing else "\n"
    gitignore.write_text(existing + prefix + f"{entry}\n")
    click.echo(f"  ✓ added {entry} to .gitignore")


# --- per-harness native installers ------------------------------------------

MARKER = "quetzal-docs-reminder.sh"


def _install_claude_code(repo: Path, quetzal_bin: str, force: bool) -> None:
    hook = repo / ".claude" / "hooks" / MARKER
    _write_hook_script(hook, quetzal_bin, "claude-code", force, "Claude Code Stop hook")
    _merge_nested_stop_hook(repo / ".claude" / "settings.json", str(hook), MARKER)
    _write_if_absent(
        repo / ".claude" / "skills" / "document-module" / "SKILL.md", SKILL_TEMPLATE, force, "document-module skill"
    )


def _install_codex(repo: Path, quetzal_bin: str, force: bool) -> None:
    hook = repo / ".codex" / "hooks" / MARKER
    _write_hook_script(hook, quetzal_bin, "codex", force, "Codex Stop hook")
    _merge_nested_stop_hook(repo / ".codex" / "hooks.json", str(hook), MARKER)
    click.echo("  ↳ run Codex's /hooks command to trust this project-local hook before it fires.")


def _install_cursor(repo: Path, quetzal_bin: str, force: bool) -> None:
    hook = repo / ".cursor" / "hooks" / MARKER
    _write_hook_script(hook, quetzal_bin, "cursor", force, "Cursor stop hook")
    _merge_cursor_hook(repo / ".cursor" / "hooks.json", str(hook), MARKER)


def _install_opencode(repo: Path, quetzal_bin: str, force: bool) -> None:
    plugin = repo / ".opencode" / "plugin" / "quetzal-docs-reminder.js"
    _write_if_absent(
        plugin, OPENCODE_PLUGIN_TEMPLATE.format(quetzal_bin=quetzal_bin), force, "opencode plugin"
    )
    click.echo("  ↳ opencode's nudge is a notification (its plugin model can't block a finished session).")


_INSTALLERS = {
    "claude-code": _install_claude_code,
    "codex": _install_codex,
    "cursor": _install_cursor,
    "opencode": _install_opencode,
}


@click.command()
@click.option(
    "--agent",
    "-a",
    type=click.Choice(AGENTS),
    default=None,
    help="Harness to install the native hook for (asked if omitted).",
)
@click.option(
    "--target-repo",
    "-t",
    "target_repo",
    type=click.Path(file_okay=False, path_type=Path),
    default=".",
    help="The codebase to benchmark (default: current directory).",
)
@click.option("--force", is_flag=True, help="Overwrite existing files.")
@click.option("--no-hooks", "no_hooks", is_flag=True, help="Config only — skip the keep-docs-fresh hook.")
@click.option("--git-hook", "git_hook", is_flag=True, help="Also install a harness-agnostic git pre-commit hook.")
@click.option(
    "--readme-detail",
    "readme_detail",
    type=click.Choice(list(README_PRESETS)),
    default=None,
    help="How long module READMEs may be, scaled by module size (asked if omitted).",
)
def main(
    agent: str | None,
    target_repo: Path,
    force: bool,
    no_hooks: bool,
    git_hook: bool,
    readme_detail: str | None,
) -> None:
    """Scaffold quetzal.toml, suites/, results/, and a native keep-docs-fresh hook."""
    repo = target_repo.expanduser().resolve()
    if not repo.is_dir():
        raise click.UsageError(f"Target repo is not a directory: {repo}")

    click.echo(f"Setting up Quetzal in {repo}\n")

    # Resolve interactive choices up front.
    if not no_hooks and agent is None:
        agent = click.prompt(
            "Which agent harness runs the keep-docs-fresh hook?",
            type=click.Choice(AGENTS),
            default="claude-code",
            show_choices=True,
        )

    toml_path = repo / "quetzal.toml"
    will_write_toml = force or not toml_path.exists()
    if will_write_toml and not no_hooks and readme_detail is None:
        readme_detail = click.prompt(
            "How detailed should module READMEs be? Budget scales with module size",
            type=click.Choice(list(README_PRESETS)),
            default="balanced",
            show_choices=True,
        )

    docs_block = _docs_check_block(readme_detail) if (will_write_toml and readme_detail) else ""
    _write_if_absent(toml_path, QUETZAL_TOML_TEMPLATE + docs_block, force, "quetzal.toml")
    (repo / "suites").mkdir(exist_ok=True)
    (repo / "results").mkdir(exist_ok=True)
    click.echo("  ✓ suites/ and results/ ready")
    _ensure_gitignore(repo, "results")

    if no_hooks:
        click.echo("  • keep-docs-fresh hook: skipped (--no-hooks)")
    else:
        quetzal_bin = shutil.which("quetzal") or "quetzal"
        click.echo(f"\nInstalling the {agent} keep-docs-fresh hook:")
        _INSTALLERS[agent](repo, quetzal_bin, force)

    if git_hook:
        if not (repo / ".git").is_dir():
            click.echo("  • git pre-commit hook: not a git repo, skipped")
        else:
            quetzal_bin = shutil.which("quetzal") or "quetzal"
            pc = repo / ".git" / "hooks" / "pre-commit"
            script = GIT_PRECOMMIT_TEMPLATE.format(quetzal_bin=quetzal_bin)
            if _write_if_absent(pc, script, force, "git pre-commit hook"):
                _make_executable(pc)

    click.echo("\nAnswerer harnesses detected:")
    from quetzal.agents import available_agents

    for name, ok in available_agents().items():
        click.echo(f"  {'✓' if ok else '✗'} {name}")

    click.echo(
        "\nNext: add a suite under [suites] in quetzal.toml, write questions "
        "(quetzal ui), then `quetzal run --all`."
    )
