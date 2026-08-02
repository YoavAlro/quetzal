from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from quetzal.core.repo_usage import inventory_repo
from quetzal.models import TokenUsage
from quetzal.pricing import PriceBook


class RepoUsageAndPricingTests(unittest.TestCase):
    def test_inventory_classifies_assets_and_prunes_generated_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("docs")
            skill = root / ".claude" / "skills" / "review" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("skill")
            hook = root / ".codex" / "hooks" / "stop.py"
            hook.parent.mkdir(parents=True)
            hook.write_text("hook")
            settings = root / ".claude" / "settings.json"
            settings.write_text('{"hooks": {"Stop": [{"command": "check"}]}}')
            ignored = root / "node_modules" / "ignored.md"
            ignored.parent.mkdir()
            ignored.write_text("ignored")

            inventory = inventory_repo(root)
            self.assertEqual(inventory.markdown_files, (".claude/skills/review/SKILL.md", "README.md"))
            self.assertEqual(inventory.skill_files, (".claude/skills/review/SKILL.md",))
            self.assertEqual(inventory.hook_files, (".claude/settings.json", ".codex/hooks/stop.py"))

    def test_price_book_uses_longest_prefix_and_cached_discount(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.json"
            path.write_text(
                json.dumps(
                    {
                        "models": {
                            "model": {"input_per_mtok": 10, "output_per_mtok": 20},
                            "model-fast": {
                                "input_per_mtok": 4,
                                "cached_input_per_mtok": 1,
                                "output_per_mtok": 8,
                            },
                        }
                    }
                )
            )
            book = PriceBook.load(path)
            usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000, cached_input_tokens=250_000)
            self.assertEqual(book.estimate("provider/model-fast-v2", usage), 7.25)


if __name__ == "__main__":
    unittest.main()
