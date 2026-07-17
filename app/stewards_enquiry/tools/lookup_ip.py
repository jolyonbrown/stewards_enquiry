"""lookup_ip — IP reputation from the bundled offline feed.

Reads fixtures/ip_reputation.json, returning the ``_default`` entry on a
miss. Hard rule from CLAUDE.md: v1 never calls an external reputation API —
live mode uses this same fixture file (a real feed is a stretch goal).
"""

import json

from telemetry import traced
from tools._shared import fixtures_dir


@traced
def lookup_ip(ip: str) -> dict:
    """Return reputation data for `ip`; unknown IPs get the `_default` entry."""
    table = json.loads((fixtures_dir() / "ip_reputation.json").read_text())
    ip = ip.strip()
    # Keys starting with "_" are metadata (_default, _comment), never direct hits.
    entry = table.get(ip) if not ip.startswith("_") else None
    known = entry is not None
    if entry is None:
        entry = table["_default"]
    return {"ip": ip, "known": known, **entry}
