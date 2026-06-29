"""Judge prompt and structured verdict schema.

Intent:
    Compare a candidate answer to the ground truth for a codebase question and
    return a single structured verdict (correct + 1-5 score + justification).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class JudgeVerdict(BaseModel):
    """Structured output the judge model must return."""

    correct: bool = Field(description="True if the answer is factually correct and addresses the question.")
    score: int = Field(description="Quality from 1 (wrong/irrelevant) to 5 (fully correct and complete).", ge=1, le=5)
    justification: str = Field(
        description="One or two sentences explaining the score, citing the key discrepancy if any."
    )


JUDGE_PROMPT = """You are grading an answer to a question about a codebase.

Judge only against the GROUND TRUTH below. Reward answers that are factually correct
and address the question; do not reward extra unverifiable detail, and do not penalize
correct answers for wording or for citing different-but-valid file paths. Mark `correct`
true only when the core of the answer matches the ground truth with no material error.

Scoring guide:
  5 = fully correct and complete
  4 = correct, minor omission
  3 = partially correct or missing a key point
  2 = mostly wrong
  1 = wrong or irrelevant

QUESTION ({service}):
{question}

GROUND TRUTH:
{ground_truth}

CANDIDATE ANSWER:
{answer}
"""
