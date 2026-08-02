from __future__ import annotations

import json
import unittest
from pathlib import Path

from quetzal.agents.codex import _parse_events as parse_codex
from quetzal.agents.cursor import _parse_output as parse_cursor
from quetzal.agents.opencode import _parse_events as parse_opencode
from quetzal.claude_cli import _parse_result as parse_claude
from quetzal.core.repo_usage import RepoUsageCollector


class HarnessParserTests(unittest.TestCase):
    def test_codex_modern_events_and_repo_usage(self) -> None:
        events = [
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "sed -n '1,80p' README.md"},
            },
            {"type": "item.completed", "item": {"type": "agent_message", "text": "answer"}},
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20},
            },
        ]
        parsed = parse_codex("\n".join(json.dumps(event) for event in events), track_repo_usage=True)
        self.assertEqual(parsed.answer, "answer")
        self.assertEqual(parsed.usage.total_tokens, 120)
        self.assertEqual(parsed.usage.cached_input_tokens, 40)
        self.assertIn("README.md", parsed.repo_usage.markdown_files)

    def test_codex_command_output_does_not_count_as_usage(self) -> None:
        event = {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "rg --files -g '*.md'",
                "aggregated_output": "README.md\ndocs/design.md\ndocs/kickoff-prompt.md",
            },
        }
        parsed = parse_codex(json.dumps(event), track_repo_usage=True)
        self.assertEqual(parsed.repo_usage.markdown_files, ())

    def test_cursor_stream_events(self) -> None:
        events = [
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "answer"}]}},
            {"type": "result", "result": "answer", "usage": {"inputTokens": 3, "outputTokens": 2}},
        ]
        parsed = parse_cursor("\n".join(json.dumps(event) for event in events))
        self.assertEqual(parsed.answer, "answer")
        self.assertEqual(parsed.data["usage"]["inputTokens"], 3)

    def test_opencode_step_usage_is_summed(self) -> None:
        events = [
            {"part": {"type": "step-finish", "tokens": {"input": 10, "output": 2}, "cost": 0.1}},
            {"part": {"type": "step-finish", "tokens": {"input": 20, "output": 3}, "cost": 0.2}},
            {"part": {"type": "text", "text": "answer"}},
        ]
        parsed = parse_opencode("\n".join(json.dumps(event) for event in events))
        self.assertEqual(parsed.answer, "answer")
        self.assertEqual(parsed.usage.total_tokens, 35)
        self.assertAlmostEqual(parsed.cost, 0.3)

    def test_claude_stream_result_and_tool_trace(self) -> None:
        collector = RepoUsageCollector(Path.cwd())
        events = [
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "README.md"}}]},
            },
            {"type": "result", "result": "answer", "usage": {"input_tokens": 1, "output_tokens": 1}},
        ]
        result = parse_claude("\n".join(json.dumps(event) for event in events), collector)
        self.assertEqual(result["result"], "answer")
        self.assertIn("README.md", collector.result().markdown_files)


if __name__ == "__main__":
    unittest.main()
