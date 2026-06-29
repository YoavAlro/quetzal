# 🪶 Quetzal

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

```bash
git clone <your-fork-url> quetzal && cd quetzal
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Requires Python 3.12+. To answer questions you need at least one agent CLI installed and
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

Edit `quetzal.toml`:

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
| `quetzal.toml` | Target repo, suites dir, results dir, suite → code-roots map |

Adding a new answerer = a new `AgentClient` in `quetzal/agents/` plus one line in its registry. Keep
answers read-only; read telemetry from the harness's own report.

## License

MIT — see [LICENSE](LICENSE).
