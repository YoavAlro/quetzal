"""Claude Code judge (headless).

Grades a candidate answer against ground truth by asking `claude -p` for a
JSON verdict. Lets the whole pipeline run wherever Claude Code is installed,
with no API/provider credentials.

Assumptions:
    `claude` is on PATH and authenticated. Grading is pure text reasoning, so
    no repo tools are needed.
"""

from __future__ import annotations

import json
import re
import shutil
from typing import ClassVar

from quetzal.claude_cli import run_claude
from quetzal.judge.prompt import JUDGE_PROMPT, JudgeVerdict

_FORMAT = (
    "\n\nRespond with ONLY a single-line JSON object — no markdown, no prose:\n"
    '{"correct": true or false, "score": <integer 1-5>, "justification": "<one or two sentences>"}'
)


class ClaudeCodeJudge:
    name: ClassVar[str] = "claude-code"

    def __init__(self, model: str | None = None):
        self.model = model
        self.model_id = f"claude-code:{model or 'default'}"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("claude") is not None

    def judge(self, question: str, ground_truth: str, answer: str, service: str) -> JudgeVerdict:
        prompt = (
            JUDGE_PROMPT.format(
                service=service, question=question, ground_truth=ground_truth, answer=answer or "(no answer produced)"
            )
            + _FORMAT
        )
        data = run_claude(prompt, self.model, "claude judge").data
        return _parse_verdict(data.get("result", ""))


def _parse_verdict(result_text: str) -> JudgeVerdict:
    match = re.search(r"\{.*\}", result_text, re.DOTALL)
    if not match:
        raise RuntimeError(f"judge returned no JSON verdict: {result_text[:200]}")
    obj = json.loads(match.group(0))
    score = max(1, min(5, int(obj.get("score", 1))))
    return JudgeVerdict(
        correct=bool(obj.get("correct", False)),
        score=score,
        justification=str(obj.get("justification", "")),
    )
