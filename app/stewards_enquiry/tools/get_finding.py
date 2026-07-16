"""get_finding — load the full GuardDuty finding. The agent's first tool call.

Fixture mode (default) scans fixtures/findings/*.json and returns the finding
whose ``id`` matches; the filename stem (e.g. "ssh-bruteforce") is accepted as
a convenience alias. Live mode (guardduty:GetFindings, read-only) is stretch
goal C and deliberately unimplemented until then.
"""

import json

from telemetry import traced
from tools._shared import fixtures_dir, live_mode


@traced
def get_finding(finding_id: str) -> dict:
    """Return the GuardDuty finding matching `finding_id` (id or fixture name)."""
    if live_mode():
        raise NotImplementedError(
            "Live mode (guardduty:GetFindings) is stretch goal C — unset STEWARD_LIVE"
        )
    findings_dir = fixtures_dir() / "findings"
    for path in sorted(findings_dir.glob("*.json")):
        finding = json.loads(path.read_text())
        if finding_id in (finding.get("id"), path.stem):
            return finding
    known = ", ".join(sorted(p.stem for p in findings_dir.glob("*.json")))
    raise ValueError(f"No fixture finding matches {finding_id!r}. Known findings: {known}")
