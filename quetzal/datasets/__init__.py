"""Question datasets — one suite per code area.

Question content is stored as JSON under the configured suites dir
(one <suite>.json per suite) and accessed through store.py, so the management
UI and the benchmark runner share one source of truth. services.py exposes the
suite -> code-root mapping loaded from quetzal.toml.
"""

from quetzal.datasets.services import SERVICE_ROOTS
from quetzal.datasets.store import (
    all_cases,
    delete_case,
    get_cases,
    list_services,
    load_cases,
    save_cases,
    service_hint,
    upsert_case,
)

__all__ = [
    "SERVICE_ROOTS",
    "all_cases",
    "delete_case",
    "get_cases",
    "list_services",
    "load_cases",
    "save_cases",
    "service_hint",
    "upsert_case",
]
