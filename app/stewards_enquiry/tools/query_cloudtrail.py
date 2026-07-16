"""query_cloudtrail — recent CloudTrail activity for a principal.

Fixture mode filters fixtures/cloudtrail_events.json by principal and time
window. For determinism the window is anchored at the principal's newest
event, not wall-clock now — offline runs must not decay as fixtures age.
Returns at most 50 events, newest first (hard rule from CLAUDE.md). Live mode
(cloudtrail:LookupEvents, read-only) is stretch goal C.
"""

import json
from datetime import datetime, timedelta

from telemetry import traced
from tools._shared import fixtures_dir, live_mode

MAX_EVENTS = 50


@traced
def query_cloudtrail(principal: str, hours: int = 24) -> list[dict]:
    """Return `principal`'s CloudTrail events within `hours` of its newest event."""
    if live_mode():
        raise NotImplementedError(
            "Live mode (cloudtrail:LookupEvents) is stretch goal C — unset STEWARD_LIVE"
        )
    if hours <= 0:
        raise ValueError("hours must be a positive integer")
    table = json.loads((fixtures_dir() / "cloudtrail_events.json").read_text())
    events = table.get(principal)
    if not isinstance(events, list):  # unknown principal, or a metadata key
        return []

    def when(event: dict) -> datetime:
        return datetime.fromisoformat(event["eventTime"])

    cutoff = max(when(e) for e in events) - timedelta(hours=hours)
    window = sorted((e for e in events if when(e) >= cutoff), key=when, reverse=True)
    return window[:MAX_EVENTS]
