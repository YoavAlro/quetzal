# Kick-off prompt for your repo

The fastest way to stand Quetzal up on a codebase is to let a coding agent do it. Paste one of the
prompts below into your agent (Claude Code, Codex, Cursor, or opencode) **from the root of the repo
you want to benchmark**. Each prompt is self-contained — swap `<this-harness>` for whichever agent
you're running.

---

## 1. Set up Quetzal on this repo

```text
Set up the `quetzal-eval` benchmark on this repository. Do each step and report the result:

1. Install and confirm the CLI:
   - `uv tool install quetzal-eval`  (or `pip install quetzal-eval`)
     - If uv reports "No solution found" for a version you know is published, its
       index cache is stale — add `--refresh` (and `--force` to replace an
       installed copy): `uv tool install quetzal-eval --refresh --force`.
   - `quetzal --version`
   - `quetzal agents`      (shows which harness CLIs are installed)

2. From the repo root, run `quetzal init` — pick THIS harness when asked, and a README-detail
   level (concise / balanced / thorough). Then show the generated quetzal.toml and list the hook
   files it installed.

3. Choose ONE meaningful code area that actually exists in this repo and register it as a suite in
   quetzal.toml under [suites], e.g. `core = ["src/core"]`.

4. Write 3 benchmark questions for that suite in suites/<suite>.json. For each: a specific question
   about that code area, plus a `ground_truth` answer DERIVED FROM THE CODE — read the files and
   cite the key files/functions it comes from. Set "reviewed": false. Don't guess; if you can't
   ground an answer in the code, choose a different question.

5. Run the pipeline on just that suite (keep it cheap with --limit):
   - `quetzal run --suite <suite> --agent <this-harness> --limit 3`   (note the session id printed)
   - `quetzal score <session-id>`
   - `quetzal report <session-id>`

6. Summarize: accuracy, average tokens/cost per question, and any question the agent got wrong —
   a wrong answer is a signal that part of the codebase is hard to navigate or under-documented.
```

After this you can add more suites via `quetzal ui` (a local web console) and re-run.

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
