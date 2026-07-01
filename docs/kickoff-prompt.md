# Kick-off prompt for your repo

The fastest way to stand Quetzal up on a codebase is to let a coding agent do it. Paste one of the
prompts below into your agent (Claude Code, Codex, Cursor, or opencode) **from the root of the repo
you want to benchmark**. Each prompt is self-contained — swap `<this-harness>` for whichever agent
you're running.

---

## 1. Learn this repo and generate an eval suite

This is the main one: the agent explores the codebase, writes benchmark questions with
**code-derived** ground truth, and runs a first benchmark. Paste it from the repo root.

```text
Set up Quetzal on this repository, then learn the codebase and generate an eval suite we can
benchmark a coding agent against. Work through the phases and report as you go.

PHASE 0 — Install & init:
- `uv tool install quetzal-eval` (or `pip install quetzal-eval`). If uv says "No solution found"
  for a version you know is published, its index cache is stale — add `--refresh --force`.
- `quetzal --version`, then `quetzal agents`.
- From the repo root run `quetzal init` — pick THIS harness and a README-detail level.

PHASE 1 — Explore (actually read the code, don't skim):
- Map the repo: top-level layout, the main modules/packages, entry points, and the key data and
  control flows. Identify 2–4 distinct code areas worth benchmarking (e.g. an auth module, a
  request pipeline, a storage layer).
- For each area, read the files that define its behavior: public API, important functions, config,
  error handling, and any non-obvious logic. Note the specific files/functions as you go.

PHASE 2 — Register suites:
- In quetzal.toml under [suites], add one entry per area mapping a short suite name to its code
  root(s), e.g. `auth = ["src/auth"]`, `pipeline = ["src/pipeline", "src/queue"]`.

PHASE 3 — Write questions (the important part):
For each suite, write ~5 questions in suites/<suite>.json (a JSON list). Spread across difficulty
(easy / medium / hard) and types:
  - "How does <feature> work?" (a flow spanning a few files)
  - "Where / in which function is <behavior> implemented?"
  - "What happens when <specific input / edge case / error>?"
  - "Why is <non-obvious design choice> done this way?" (only if the code or comments show it)

Rules for GOOD eval questions:
  - Answerable ONLY by reading THIS repo's code — not from general knowledge, and not guessable
    from the wording. Don't leak the answer into the question.
  - Each has a single, checkable answer. Avoid vague/subjective questions a judge can't grade.
  - ground_truth: 2–4 sentences stating what a correct answer MUST contain, DERIVED FROM THE CODE
    you read, and citing the key files/functions (e.g. "see refresh_token() in
    src/auth/tokens.py"). If you can't ground it in code, drop the question.

Each case has this shape:
  {
    "id": "<suite>_<short_slug>",
    "service": "<suite>",
    "question": "...",
    "ground_truth": "Derived from the code: ... (cite files/functions).",
    "difficulty": "easy|medium|hard",
    "tags": ["..."],
    "reviewed": false
  }
Keep "reviewed": false — these are drafts a human confirms later.

PHASE 4 — Smoke-test & report:
- Sanity-check the pipeline cheaply: `quetzal run --all --agent <this-harness> --limit 3`
  (--limit caps the TOTAL questions run, so this runs 3 across all suites — enough to confirm it
  works end to end; note the session id it prints).
- `quetzal score <session-id>` then `quetzal report <session-id>`.
- Report: the suites you created and how many questions each has; the smoke-run accuracy and
  tokens/cost; and any answer that looks mis-graded (usually means the ground_truth needs
  tightening, not that the agent was wrong).

Finally, tell me to review the drafts in `quetzal ui`, flip the solid ones to "reviewed": true,
and then run the full benchmark with `quetzal run --all`.
```

Two notes: ground truth is only as trustworthy as the reading behind it — skim the report for
mis-grades and tighten those cases. And keep `reviewed: false` until a human has eyeballed each one;
that flag is what separates drafts from a benchmark you trust.

---

## 2. Verify the keep-docs-fresh hook

Run this after step 1 to confirm the documentation nudge works. It calls `quetzal docs-check`
directly, so it's a deterministic pass/fail regardless of harness quirks.

```text
Verify the Quetzal keep-docs-fresh hook. Run these as commands and report each result:

1. Create a new module with no README:
   `mkdir -p libs/scratch_probe && printf '[project]\nname="scratch_probe"\n' > libs/scratch_probe/pyproject.toml`
2. Run `quetzal docs-check --format json`
   → EXPECT {"nudge": true, ...} telling you to document libs/scratch_probe.
3. Write a real README.md inside libs/scratch_probe/ describing the module, then run
   `quetzal docs-check --format json` again
   → EXPECT {"nudge": false, ...} — the module is documented, the nudge clears.
4. Clean up: `rm -rf libs/scratch_probe`.

Report whether both assertions passed.
```

> **Seeing the hook fire automatically.** The prompt above tests the engine directly. To watch the
> hook *block a turn and inject the nudge on its own*, start a **fresh** agent session in this repo
> after `quetzal init` — a harness only picks up newly installed hooks on session start, so
> mid-session installs won't be active until it reloads its settings.
