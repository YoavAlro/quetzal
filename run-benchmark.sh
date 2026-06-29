#!/usr/bin/env bash
# Convenience wrapper for the full local pipeline: RUN -> SCORE -> REPORT.
#
#   ./run-benchmark.sh <suite>        # one suite, Claude Code (default)
#   ./run-benchmark.sh --all          # every suite
#   AGENT=codex ./run-benchmark.sh <suite>          # a different answerer harness
#   JUDGE_MODEL=claude-sonnet-4-5 ./run-benchmark.sh <suite>   # pin the judge model
#
# Answerer: a real coding-agent CLI run headless (Claude Code by default; set
# AGENT=codex / cursor / opencode). Judge: the claude-code backend (no API creds).
set -euo pipefail
cd "$(dirname "$0")"

AGENT="${AGENT:-claude-code}"
JUDGE="${JUDGE:-claude-code}"
MODEL_ARG=();       [[ -n "${MODEL:-}" ]] && MODEL_ARG=(--model "$MODEL")
JUDGE_MODEL_ARG=(); [[ -n "${JUDGE_MODEL:-}" ]] && JUDGE_MODEL_ARG=(--judge-model "$JUDGE_MODEL")

if [[ "${1:-}" == "--all" ]]; then
  SELECTOR=(--all)
elif [[ -n "${1:-}" ]]; then
  SELECTOR=(--suite "$1")
else
  echo "usage: $0 <suite>|--all   (env: AGENT, MODEL, JUDGE, JUDGE_MODEL)" >&2
  exit 1
fi

SESSION="quetzal-$(date +%Y%m%d-%H%M%S)"
quetzal run "${SELECTOR[@]}" --agent "$AGENT" "${MODEL_ARG[@]}" --session "$SESSION"
quetzal score "$SESSION" --judge "$JUDGE" "${JUDGE_MODEL_ARG[@]}"
quetzal report "$SESSION"
