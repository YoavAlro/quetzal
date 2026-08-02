from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quetzal.datasets.store import SuiteFullError, load_cases, upsert_case
from quetzal.models import QuestionCase


class StoreTests(unittest.TestCase):
    def test_suite_cap_blocks_growth_but_allows_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("quetzal.datasets.store.DATA_DIR", Path(directory)),
                patch("quetzal.datasets.store.MAX_CASES_PER_SUITE", 1),
            ):
                first = QuestionCase("one", "suite", "q", "g")
                upsert_case("suite", first)
                with self.assertRaises(SuiteFullError):
                    upsert_case("suite", QuestionCase("two", "suite", "q", "g"))
                upsert_case("suite", QuestionCase("one", "suite", "updated", "g"))
                self.assertEqual(load_cases("suite")[0].question, "updated")


if __name__ == "__main__":
    unittest.main()
