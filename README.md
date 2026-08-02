<p align="center">
  <img src="assets/quetzal-logo.png" alt="Quetzal" width="420">
</p>

<p align="center"><em>the feathered serpent · asks · judges · reports</em></p>

**Measure how well — and how cheaply — a coding-agent harness answers questions about your codebase.**

Quetzal points a real coding-agent CLI (Claude Code, Codex, Cursor, opencode) at a repository,
asks it questions you've written, and judges each answer against a ground-truth answer. It reports
**accuracy, token/cache usage, latency, cost, and repository-context usage per suite** — so you can
see whether your docs make an agent faster and cheaper, compare models/harnesses, or catch when a
change makes part of the codebase harder to navigate.

It drives the **actual harness** — its system prompt, tools, and planning loop — not a raw-API
reimplementation, because the harness is the thing worth measuring.

```
1. RUN     quetzal run      answer questions with an agent harness   → answer + harness telemetry
2. SCORE   quetzal score    judge answers vs ground truth            → correct? + 1–5 score
3. REPORT  quetzal report   aggregate per suite + overall            → accuracy, tokens, time, cost, context
```

## What's new in 0.3.0

- **Hardened harness adapters:** current Codex JSONL parsing and isolation, Cursor ask-mode sandboxing,
  OpenCode plan/pure JSON telemetry, and shared Claude Code error handling.
- **Comparable telemetry:** cached-input tokens, per-question and aggregate latency, harness-billed
  cost when available, and API-equivalent estimated cost otherwise.
- **Reproducible and recoverable runs:** git commit/branch/dirty provenance, provider and reasoning
  metadata, bounded suites, and `--retry-errors` without re-spending successful answers.
- **Repository-health signals:** optional Markdown/custom-skill/hook inventory plus best-effort
  observed usage in CLI reports, JSON, exports, history APIs, and the management UI.
- **Portable results:** `quetzal export <session-id>` creates one shareable `bundle.json` containing
  configuration, provenance, report aggregates, and every case.

This release ports the reusable behavior from Emerix's original benchmark while keeping private
provider integrations and private suites in the monorepo. See the full
[capability matrix and cutover plan](docs/emerix-migration.md).

## Install

As a standalone tool on your `PATH` (recommended) — no venv to manage:

```bash
uv tool install quetzal-eval      # or: pipx install quetzal-eval
quetzal --version
```

Upgrade an existing tool installation:

```bash
uv tool upgrade quetzal-eval      # or: pipx upgrade quetzal-eval
```

The distribution is `quetzal-eval` on PyPI; the command it installs is `quetzal`. Or for
development, editable from a clone:

```bash
git clone https://github.com/YoavAlro/quetzal && cd quetzal
python3 -m venv .venv && source .venv/bin/activate
pip install -e . ruff build
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

For a read-only Codex smoke with full 0.3.0 telemetry:

```bash
quetzal run --suite quetzal --limit 1 --agent codex \
  --model gpt-5.6-sol --reasoning-effort low --track-repo-usage
```

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
max_cases_per_suite = 12             # 0 disables the recurring-cost guardrail
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
that's wrong or incomplete. By default, a suite may contain at most 12 questions: editing an
existing question is always allowed, but adding the thirteenth requires deleting/replacing a weaker
case. This bounds the recurring cost of `--all`; set `max_cases_per_suite = 0` to opt out.

Configuration discovery walks upward from the current directory for `quetzal.toml`. CI and ad-hoc
runs can override paths without editing the file:

| Environment variable | Meaning |
|---|---|
| `QUETZAL_CONFIG` | Explicit `quetzal.toml` path |
| `QUETZAL_TARGET_REPO` | Repository the answerer explores |
| `QUETZAL_SUITES_DIR` | Directory containing `<suite>.json` files |
| `QUETZAL_RESULTS_DIR` | Generated session directory |
| `QUETZAL_PRICING` | Custom JSON token-rate file used by reports/exports |

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

Codex defaults to the built-in `openai` provider (the authenticated ChatGPT license), runs
ephemerally, ignores user configuration, and disables apps/plugins so personal integrations do not
silently shape the benchmark. A custom `--provider` keeps the provider definition from Codex config
but still removes MCP servers; `--reasoning-effort` accepts `minimal`, `low`, `medium`, `high`, or
`xhigh`.

Claude Code is the reference answerer and the only judge included in the standalone package. The
private raw-API baseline and `emerix.agenticv3` judge remain Emerix integrations because they depend
on private infrastructure and do not measure the coding-agent harness itself.

## Run lifecycle and recovery

Unless `--session` is supplied, Quetzal creates a timestamped session. Reusing a session normally
replaces its old results so partial runs never mix with stale files. If a transient CLI failure
leaves only a few unanswered cases, recover them without re-spending successful answers:

```bash
quetzal run --suite auth --agent codex --session auth-run --no-score
quetzal run --suite auth --agent codex --session auth-run --retry-errors --no-score
```

For safety, a retry must match the original agent, model, provider, and repo-usage tracking setting;
Quetzal refuses to combine different benchmark configurations. A retry preserves completed answers
and overwrites only failed/missing case files.

Every new session captures:

- agent client, model, optional provider, and reasoning effort;
- selected suites and start time;
- target repository commit, branch, and dirty state;
- optional repository-context inventory.

Scoring is incremental too: already judged answers are skipped unless `quetzal score --force` is
used. If the judge fails on its first three cases, scoring aborts early instead of repeating the
same authentication/model configuration error across the whole session.

## Pricing, time, and token accounting

Reports include total/cached input tokens, output tokens, average and total answering time, and
dollar cost where possible. Claude Code and OpenCode can report their own cost; other harnesses are
priced from tokens using Quetzal's packaged `pricing.json`.

- `$1.23` is a cost reported by the harness.
- `~$1.23` is an **API-equivalent estimate**, not a subscription charge.
- `—` means neither the harness nor the price book supplied enough information.

Override rates with `quetzal report --pricing rates.json`, `quetzal export --pricing rates.json`, or
`QUETZAL_PRICING`. A rate file maps model IDs (exactly or by longest prefix) to USD per million
tokens; cached input is optional:

```json
{
  "models": {
    "my-model": {
      "input_per_mtok": 2.5,
      "cached_input_per_mtok": 0.25,
      "output_per_mtok": 15.0
    }
  }
}
```

## Repository context usage

Pass `--track-repo-usage` to correlate benchmark health with repository maintenance:

```bash
quetzal run --suite auth --agent codex --track-repo-usage
```

Quetzal records two different measurements:

- **Inventory at run start:** unique Markdown files, repository custom skills (`*/skills/*/SKILL.md`),
  and repository hook assets, including agent hook directories/configs, `.husky`, `.githooks`,
  pre-commit config, and Lefthook config.
- **Observed usage:** unique assets whose paths appeared in structured tool invocation inputs during
  answer turns. Report rows show this as `md/sk/hook`; `report.json` and `bundle.json` include paths.

Generated/vendor trees such as `.git`, `.quetzal`, `.venv`, `node_modules`, `dist`, `build`, and
cache directories are pruned from inventory. Tool outputs are deliberately ignored—a command that
merely lists every Markdown file does not make every file count as read.

Observed usage is best-effort. A harness may hide an internal read or hook execution, so zero means
“not visible in emitted tool inputs,” not proof that the resource had no effect. The deterministic
inventory still lets you compare repository health against accuracy, tokens, cost, and latency over
time. Categories may overlap: a `SKILL.md` is both a Markdown file and a custom skill.

## Reports and portable exports

`run` scores and reports by default, but each step remains independently repeatable:

```bash
quetzal run --suite auth --no-score --session auth-run
quetzal score auth-run
quetzal report auth-run
quetzal report auth-run --json
quetzal export auth-run
```

`report` writes `report.json` and renders per-suite/overall accuracy, score, tokens, latency, cost,
errors, and observed `md/skill/hook` counts. `export` writes `bundle.json`, a single shareable file
with schema version, session config, git provenance, the full report, and every question, ground
truth, answer, usage record, error, observed context, and judge verdict.

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

- `config.json` — agent/model/provider/effort settings, suites, timestamps, git provenance, and
  optional repository inventory.
- `<suite>/<case-id>.json` — question/ground truth, answer, fresh/cached/output tokens, model, agent,
  harness cost, latency, observed repo usage, judge evaluation, or a persisted error.
- `report.json` — per-suite and overall accuracy, scores, tokens, latency, billed/estimated cost,
  errors, inventory, and observed-context counts/paths.
- `bundle.json` — optional versioned single-file export created by `quetzal export <session-id>`.

Older result files remain loadable: missing cache/context/provenance fields receive safe defaults.

## How it's organized

| Area | What it does |
|------|--------------|
| `quetzal/agents/` | `AgentClient` adapters that shell out to coding-agent CLIs (lazy registry) |
| `quetzal/claude_cli.py` | Shared Claude Code invocation and actionable stdout/stderr error handling |
| `quetzal/judge/` | Judge prompt + the Claude Code judge that grades against ground truth |
| `quetzal/core/` | Run/retry loop, git provenance, repo-context observation, JSON storage |
| `quetzal/datasets/` | JSON-backed question store (shared by runner + UI) |
| `quetzal/ui/` | Build-free local web console |
| `quetzal/{cli,score,report,main}.py` | The pipeline entry points |
| `quetzal/init_cmd.py` | `quetzal init` — scaffold config, suites/results dirs, the keep-docs-fresh hook + skill |
| `quetzal/docs_check.py` | `quetzal docs-check` — the new-module-without-docs nudge behind the hook |
| `quetzal/pricing.py` | API-equivalent estimates for harnesses that report tokens but no cost |
| `quetzal/export.py` | Portable session bundle generation |
| `quetzal.toml` | Target repo, suites dir, results dir, suite → code-roots map |

Adding a new answerer = a new `AgentClient` in `quetzal/agents/` plus one line in its registry. Keep
answers read-only; read telemetry from the harness's own report.

## Development and verification

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

ruff check quetzal tests
python -m unittest discover -s tests -v
node --check quetzal/ui/static/app.js
python -m build
```

The test suite covers backward-compatible session loading, modern events from all four adapters,
input-only repository tracing, inventory pruning/classification, cached-token pricing, aggregate
reporting, and suite-cap replacement behavior.

## License

MIT — see [LICENSE](LICENSE).
