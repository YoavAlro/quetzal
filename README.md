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
uv tool install quetzal-eval      # or: pipx install quetzal-eval
quetzal --version
```

The distribution is `quetzal-eval` on PyPI; the command it installs is `quetzal`. Or for
development, editable from a clone:

```bash
git clone https://github.com/YoavAlro/quetzal && cd quetzal
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
quetzal run --all --agent claude-code     # answer → judge → report, in one command
```

By default `run` answers every question, **judges** the answers, and prints the **report** — the
whole pipeline. Stop earlier with `--no-score` (just answer) or `--no-report`, and pin the judge
with `--judge` / `--judge-model`. The individual steps are still there if you want them separately:

```bash
quetzal run --all --no-score              # just answer (prints the <session-id>)
quetzal score <session-id>                # judge later
quetzal report <session-id>               # re-print the summary
```

Smoke a single suite without spending much: `quetzal run --suite quetzal --limit 2`.

## Point it at your own codebase

> **In a hurry?** Hand your coding agent the [kick-off prompt](docs/kickoff-prompt.md) — it installs
> Quetzal, runs `init`, **explores your code to generate an eval suite** (questions + code-derived
> ground truth), and runs a first benchmark for you.

Run `init` from inside the repo you want to benchmark — it scaffolds everything:

```bash
cd /path/to/your/repo
quetzal init                       # asks which agent harness to wire the keep-docs-fresh hook for
quetzal init --agent codex         # or pick non-interactively (claude-code | codex | cursor | opencode)
quetzal init --git-hook            # also install a harness-agnostic git pre-commit hook
quetzal init --no-hooks            # config only, skip the hook
```

`init` scaffolds `quetzal.toml`, `suites/`, `.quetzal/results/`, installs the keep-docs-fresh hook **native
to your chosen harness** (see below), and prints which agent CLIs it found. It's idempotent
(existing files are left as-is unless `--force`). It then leaves you with a `quetzal.toml` to fill
in — map each code area you care about to a suite:

```toml
target_repo = "/path/to/your/repo"   # the codebase under test
suites_dir  = "suites"               # one <suite>.json per suite (curated, committed)
results_dir = ".quetzal/results"     # benchmark sessions (generated, git-ignored)

[suites]
# suite name -> code root(s) relative to target_repo (the agent's starting hint)
auth     = ["services/auth"]
billing  = ["services/billing", "libs/money"]

[evaluation]
max_cases_per_suite = 12          # 0 disables the recurring-cost guardrail
```

Then write questions. Use the UI (below) or drop a `suites/<name>.json` file — a list of:

```json
{
  "id": "auth_token_refresh",
  "service": "auth",
  "question": "How are refresh tokens rotated?",
  "ground_truth": "Derived from the code: on each refresh the old token is revoked and ...",
  "difficulty": "medium",
  "tags": ["tokens"]
}
```

Ground truth should be **derived from the code**, not guessed, so the benchmark can detect a doc
that's wrong or incomplete. Every value in `quetzal.toml` is overridable by env var (`QUETZAL_TARGET_REPO`,
`QUETZAL_SUITES_DIR`, `QUETZAL_RESULTS_DIR`, `QUETZAL_CONFIG`) for CI and ad-hoc runs.

## Agents (answerer) and the judge

`--agent` selects the harness; `--model` is passed through to it (default: the CLI's own default).

| Agent | CLI | Read-only enforcement | Token + cost telemetry |
|-------|-----|------------------------|------------------------|
| `claude-code` (default) | `claude -p` JSON/stream JSON | `--allowedTools Read Grep Glob LS` | tokens, cache reads, billed cost, latency |
| `codex` | `codex exec --json --ephemeral` | read-only sandbox; plugins/apps off | tokens, cache reads, estimated cost, latency |
| `cursor` | `cursor-agent -p` JSON/stream JSON | ask mode + sandbox | tokens/cache when reported, estimated cost, latency |
| `opencode` | `opencode run --format json` | plan agent + `--pure` | tokens, cache reads, harness cost, latency |

The **judge** defaults to `claude-code` too (`quetzal score --judge claude-code`) — it shells out to
`claude -p` for a structured verdict, so **no API keys are required** anywhere in the pipeline. Pin
the judge model with `--judge-model`.

Answerers always run **read-only** (enforced per CLI, never by trusting the model). Quetzal never
passes a skip-permissions flag.

Codex runs can pin both the provider and reasoning effort (`--provider`, `--reasoning-effort`). If
a transient CLI failure leaves only a few unanswered cases, recover them without re-spending the
successful answers:

```bash
quetzal run --suite auth --agent codex --session auth-run --no-score
quetzal run --suite auth --agent codex --session auth-run --retry-errors --no-score
```

Sessions capture the target repository's commit, branch, and dirty state. When a CLI reports tokens
but no dollar amount, Quetzal estimates an API-equivalent cost from its packaged `pricing.json`;
`~$` marks an estimate, not a billed subscription charge. Override rates with `--pricing` on
`report`/`export` or `QUETZAL_PRICING`.

## Repository context usage

Pass `--track-repo-usage` to correlate benchmark health with repository maintenance:

```bash
quetzal run --suite auth --agent codex --track-repo-usage
```

Quetzal records two different measurements:

- **Inventory at run start:** unique Markdown files, repository custom skills (`*/skills/*/SKILL.md`),
  and repository hook assets.
- **Observed usage:** unique assets whose paths appeared in structured tool invocation inputs during
  answer turns. Report rows show this as `md/sk/hook`; `report.json` and `bundle.json` include paths.

Observed usage is deliberately labeled best-effort. A harness may hide an internal read or hook
execution, so zero means “not visible in emitted tool events,” not proof that the resource had no
effect. The inventory is deterministic and can still be correlated against accuracy, tokens, cost,
and latency across sessions.

## Management UI

A local, build-free web console to manage question suites and view score history:

```bash
quetzal ui          # → http://127.0.0.1:8765
```

- **Questions** tab — per-suite add / edit / delete, set difficulty and tags; each suite shows its
  latest benchmark score in the sidebar. Edits write straight to the JSON suite files.
- **Score history** tab — every past run as a card and in an all-runs table (accuracy, tokens,
  cost, agent, judge, repo context), a per-suite accuracy/token trend chart, and a click-through
  breakdown with inventory and observed `md/skill/hook` counts.

Local-only, no auth — don't expose the port publicly. Styled in the Quetzal brand theme (navy +
teal→green); the palette, type, and component tokens are documented in [docs/design.md](docs/design.md).

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

`.quetzal/results/<session-id>/`:
- `config.json` — agent/model settings, git provenance, and optional repository inventory
- `<suite>/<case-id>.json` — question, answer, token/cache/cost/timing telemetry, observed repo usage, verdict
- `report.json` — per-suite and overall accuracy, telemetry, and repository-context counts
- `bundle.json` — optional single-file export created by `quetzal export <session-id>`

## How it's organized

| Area | What it does |
|------|--------------|
| `quetzal/agents/` | `AgentClient` adapters that shell out to coding-agent CLIs (lazy registry) |
| `quetzal/judge/` | Judge prompt + the Claude Code judge that grades against ground truth |
| `quetzal/core/` | Run loop, retry logic, git provenance, repo-context observation, JSON storage |
| `quetzal/datasets/` | JSON-backed question store (shared by runner + UI) |
| `quetzal/ui/` | Build-free local web console |
| `quetzal/{cli,score,report,main}.py` | The pipeline entry points |
| `quetzal/init_cmd.py` | `quetzal init` — scaffold config, suites/results dirs, the keep-docs-fresh hook + skill |
| `quetzal/docs_check.py` | `quetzal docs-check` — the new-module-without-docs nudge behind the hook |
| `quetzal/pricing.py` | API-equivalent estimates for harnesses that report tokens but no cost |
| `quetzal.toml` | Target repo, suites dir, results dir, suite → code-roots map |

Adding a new answerer = a new `AgentClient` in `quetzal/agents/` plus one line in its registry. Keep
answers read-only; read telemetry from the harness's own report.

## License

MIT — see [LICENSE](LICENSE).
