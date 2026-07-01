<p align="center">
  <img src="assets/quetzal-logo.png" alt="Quetzal" width="420">
</p>

<p align="center"><em>the feathered serpent · asks · judges · reports</em></p>

**Measure how well — and how cheaply — a coding-agent harness answers questions about your codebase.**

Quetzal points a real coding-agent CLI (Claude Code, Codex, Cursor, opencode) at a repository,
asks it questions you've written, and judges each answer against a ground-truth answer. It reports
**accuracy, token usage, and cost per suite** — so you can see whether your docs make an agent
faster and cheaper, compare models/harnesses, or catch when a change makes part of the codebase
harder to navigate.

It drives the **actual harness** — its system prompt, tools, and planning loop — not a raw-API
reimplementation, because the harness is the thing worth measuring.

```
1. RUN     quetzal run      answer questions with an agent harness   → tokens + cost per question
2. SCORE   quetzal score    judge answers vs ground truth            → correct? + 1–5 score
3. REPORT  quetzal report   aggregate per suite + overall            → accuracy %, avg tokens, cost
```

## Install

As a standalone tool on your `PATH` (recommended) — no venv to manage:

```bash
uv tool install .          # or: pipx install .   (from a clone)
quetzal --version
```

Or for development, editable in a venv:

```bash
git clone <your-fork-url> quetzal && cd quetzal
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Requires Python 3.11+. To answer questions you need at least one agent CLI installed and
authenticated — by default [Claude Code](https://docs.claude.com/claude-code) (`claude`). Check
what Quetzal can see:

```bash
quetzal agents      # ✓ / ✗ per harness: claude-code, codex, cursor, opencode
```

## Quick start (against Quetzal's own repo)

The shipped `quetzal.toml` points at this repository, with one self-referential `quetzal` suite, so
it runs out of the box:

```bash
quetzal run --all --agent claude-code     # answer every suite's questions
quetzal score <session-id> --judge claude-code
quetzal report <session-id>
```

`run` prints the `<session-id>` (e.g. `quetzal-20260629-101500`) when it finishes. Or chain all
three with the wrapper:

```bash
./run-benchmark.sh --all                  # AGENT=codex ./run-benchmark.sh quetzal
```

Smoke a single suite without spending much: `quetzal run --suite quetzal --limit 2`.

## Point it at your own codebase

> **In a hurry?** Hand your coding agent the [kick-off prompt](docs/kickoff-prompt.md) and it will
> install Quetzal, run `init`, write a first suite, and run the benchmark for you.

Run `init` from inside the repo you want to benchmark — it scaffolds everything:

```bash
cd /path/to/your/repo
quetzal init                       # asks which agent harness to wire the keep-docs-fresh hook for
quetzal init --agent codex         # or pick non-interactively (claude-code | codex | cursor | opencode)
quetzal init --git-hook            # also install a harness-agnostic git pre-commit hook
quetzal init --no-hooks            # config only, skip the hook
```

`init` scaffolds `quetzal.toml`, `suites/`, `results/`, installs the keep-docs-fresh hook **native
to your chosen harness** (see below), and prints which agent CLIs it found. It's idempotent
(existing files are left as-is unless `--force`). It then leaves you with a `quetzal.toml` to fill
in — map each code area you care about to a suite:

```toml
target_repo = "/path/to/your/repo"   # the codebase under test
suites_dir  = "suites"               # one <suite>.json per suite
results_dir = "results"

[suites]
# suite name -> code root(s) relative to target_repo (the agent's starting hint)
auth     = ["services/auth"]
billing  = ["services/billing", "libs/money"]
```

Then write questions. Use the UI (below) or drop a `suites/<name>.json` file — a list of:

```json
{
  "id": "auth_token_refresh",
  "service": "auth",
  "question": "How are refresh tokens rotated?",
  "ground_truth": "Derived from the code: on each refresh the old token is revoked and ...",
  "difficulty": "medium",
  "tags": ["tokens"],
  "reviewed": false
}
```

Ground truth should be **derived from the code**, not guessed, so the benchmark can detect a doc
that's wrong or incomplete. Cases start `reviewed: false`; flip to `true` once a human verifies the
answer. Every value in `quetzal.toml` is overridable by env var (`QUETZAL_TARGET_REPO`,
`QUETZAL_SUITES_DIR`, `QUETZAL_RESULTS_DIR`, `QUETZAL_CONFIG`) for CI and ad-hoc runs.

## Agents (answerer) and the judge

`--agent` selects the harness; `--model` is passed through to it (default: the CLI's own default).

| Agent | CLI | Read-only enforcement | Token + cost telemetry |
|-------|-----|------------------------|------------------------|
| `claude-code` (default) | `claude -p --output-format json` | `--allowedTools Read Grep Glob LS` | full (usage + `total_cost_usd`) |
| `codex` | `codex exec --json --sandbox read-only` | sandbox read-only | best-effort (parsed from events) |
| `cursor` | `cursor-agent -p --output-format json` | — | best-effort |
| `opencode` | `opencode run` | — | accuracy + latency only (no token telemetry) |

The **judge** defaults to `claude-code` too (`quetzal score --judge claude-code`) — it shells out to
`claude -p` for a structured verdict, so **no API keys are required** anywhere in the pipeline. Pin
the judge model with `--judge-model`.

Answerers always run **read-only** (enforced per CLI, never by trusting the model). Quetzal never
passes a skip-permissions flag.

## Management UI

A local, build-free web console to manage question suites and view score history:

```bash
quetzal ui          # → http://127.0.0.1:8765
```

- **Questions** tab — per-suite add / edit / delete, set difficulty and tags, flip `reviewed`
  inline. Edits write straight to the JSON suite files.
- **Score history** tab — every past run as a card (overall accuracy + avg tokens + model), a
  per-suite accuracy/token trend chart across runs, and a click-through per-suite breakdown.

Local-only, no auth — don't expose the port publicly.

## Keeping module docs fresh

Good module docs are what Quetzal's benchmark rewards — they make a coding-agent harness answer
questions about your code faster and cheaper. To keep them from rotting as the code grows, `quetzal
init` installs a **keep-docs-fresh hook using each harness's own native mechanism**. When the agent
finishes a turn it nudges on two signals:

- **Missing docs** — a **new package manifest** (`pyproject.toml`, `package.json`, `go.mod`, …)
  landed in a directory with **no README** → write documentation for that module.
- **Bloated docs** — a README **you're editing** has grown past a budget that **scales with its
  module's size** (`base + per-100-LOC × module_LOC`) → condense it: cut redundancy, move deep
  detail out, keep purpose / API / key files. A 3000-line package earns a long README; a 50-line
  helper does not.

`quetzal init` asks how detailed READMEs should be — **concise / balanced / thorough** — and writes
the matching budget into `[docs_check]`. Either way it only looks at files in the current working
set, and you can always say the change isn't warranted.

| Harness | Native integration | Installed to | Behavior |
|---------|--------------------|--------------|----------|
| `claude-code` | Stop hook | `.claude/settings.json` + `.claude/hooks/` | **blocks** the turn; fires once (`stop_hook_active` guard) |
| `codex` | Stop hook | `.codex/hooks.json` + `.codex/hooks/` | **blocks** (exit 2); run Codex `/hooks` to trust it first |
| `cursor` | `stop` hook | `.cursor/hooks.json` + `.cursor/hooks/` | auto-submits a follow-up; `loop_limit` caps re-fire |
| `opencode` | plugin | `.opencode/plugin/` | **notifies** on `session.idle` (plugins can't block a finished session) |

For `claude-code` it also drops a **`document-module` skill** (`.claude/skills/document-module/`) —
the documented way to write a module README + docstrings **derived from the code**. `quetzal init
--git-hook` adds a harness-agnostic **git pre-commit** warning on top of any of these.

All of them call one command you can also run by hand:

```bash
quetzal docs-check                      # claude-code blocking JSON (the default)
quetzal docs-check --format json        # {"nudge": bool, "dirs": [...], "reason": ...}
```

It's deliberately **high-precision, low-noise** and only ever inspects files in the working set.
Tune it in `quetzal.toml` under `[docs_check]`: `manifests = [...]` sets what counts as a "new
module", and `readme_base_lines` / `readme_lines_per_100_loc` set the size-relative condense budget
(both `0` disables the bloat nudge).

## Output

`results/<session-id>/`:
- `config.json` — run metadata (agent, model, judge, suites)
- `<suite>/<case-id>.json` — question, answer, token usage, judge verdict
- `report.json` — aggregated per-suite + overall stats

## How it's organized

| Area | What it does |
|------|--------------|
| `quetzal/agents/` | `AgentClient` adapters that shell out to coding-agent CLIs (lazy registry) |
| `quetzal/judge/` | Judge prompt + the Claude Code judge that grades against ground truth |
| `quetzal/core/` | Run loop + JSON session storage |
| `quetzal/datasets/` | JSON-backed question store (shared by runner + UI) |
| `quetzal/ui/` | Build-free local web console |
| `quetzal/{cli,score,report,main}.py` | The pipeline entry points |
| `quetzal/init_cmd.py` | `quetzal init` — scaffold config, suites/results dirs, the keep-docs-fresh hook + skill |
| `quetzal/docs_check.py` | `quetzal docs-check` — the new-module-without-docs nudge behind the hook |
| `quetzal.toml` | Target repo, suites dir, results dir, suite → code-roots map |

Adding a new answerer = a new `AgentClient` in `quetzal/agents/` plus one line in its registry. Keep
answers read-only; read telemetry from the harness's own report.

## License

MIT — see [LICENSE](LICENSE).
