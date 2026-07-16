"""Shared plumbing for the tools: fixture location and mode selection.

Invariant 4 (offline-first): the default mode reads only from fixtures/.
Live mode sits behind STEWARD_LIVE=1 and is not implemented until stretch
goal C — the tools raise rather than silently falling back to fixtures.
"""

import os
from pathlib import Path

FIXTURES_DIR_ENV = "STEWARD_FIXTURES_DIR"


def live_mode() -> bool:
    return os.environ.get("STEWARD_LIVE") == "1"


def fixtures_dir() -> Path:
    """Locate fixtures/: env override first, then walk up from this file.

    The walk handles both layouts we run in — the repo (fixtures/ at the
    root) and a deployed CodeZip (fixtures/ packaged next to main.py).
    """
    override = os.environ.get(FIXTURES_DIR_ENV)
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "fixtures"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"No fixtures/ directory found above {Path(__file__)} and {FIXTURES_DIR_ENV} is unset"
    )
