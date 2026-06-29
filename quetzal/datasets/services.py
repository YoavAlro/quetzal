"""Suite registry — the named code areas under test and their code roots.

The mapping is loaded from quetzal.toml's `[suites]` table (see config.py).
Kept as a single module-level name so the store and the UI have one import
site. `SERVICE_ROOTS` is the historical name used across those callers.
"""

from __future__ import annotations

from quetzal.config import SUITE_ROOTS

# suite name -> code root(s); empty when a suite is defined only by its JSON file.
SERVICE_ROOTS = SUITE_ROOTS
