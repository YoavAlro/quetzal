from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quetzal.core.storage import SessionStore
from quetzal.models import (
    AnswerRun,
    CaseResult,
    Evaluation,
    QuestionCase,
    RepoResources,
    SessionConfig,
    TokenUsage,
)
from quetzal.pricing import ModelPrice, PriceBook
from quetzal.report import build_report


class ModelsAndReportTests(unittest.TestCase):
    def test_old_case_result_still_loads(self) -> None:
        result = CaseResult.from_dict(
            {
                "case": {"id": "id", "service": "suite", "question": "q", "ground_truth": "g"},
                "answer_run": {
                    "answer": "a",
                    "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
                    "model": "m",
                },
            }
        )
        self.assertEqual(result.answer_run.usage.cached_input_tokens, 0)
        self.assertIsNone(result.answer_run.repo_usage)

    def test_report_includes_inventory_observed_usage_timing_and_estimated_cost(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            with patch("quetzal.core.storage.RESULTS_DIR", results):
                store = SessionStore("session")
                store.save_config(
                    SessionConfig(
                        session_id="session",
                        agent_model="model",
                        services=["suite"],
                        started_at="now",
                        repo_inventory=RepoResources(
                            markdown_files=("README.md", "docs/guide.md"),
                            skill_files=(".claude/skills/x/SKILL.md",),
                            hook_files=(".codex/hooks/stop.py",),
                        ),
                    )
                )
                store.save_result(
                    CaseResult(
                        case=QuestionCase("id", "suite", "q", "g"),
                        answer_run=AnswerRun(
                            answer="a",
                            usage=TokenUsage(100, 20, 120, 50),
                            model="model",
                            elapsed_s=2.5,
                            repo_usage=RepoResources(markdown_files=("README.md",), trace_available=True),
                        ),
                        evaluation=Evaluation(True, 5, "ok", "judge", "now"),
                    )
                )
                prices = PriceBook({"model": ModelPrice(10, 20, 1)})
                report = build_report("session", prices)

        self.assertEqual(report["repo_context"]["inventory"]["markdown_files"], 2)
        self.assertEqual(report["repo_context"]["observed_usage"]["markdown_files"], 1)
        self.assertEqual(report["overall"]["avg_elapsed_s"], 2.5)
        self.assertTrue(report["overall"]["cost_estimated"])


if __name__ == "__main__":
    unittest.main()
