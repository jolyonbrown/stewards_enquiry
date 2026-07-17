"""Golden verdict tests — loose assertions on verdict class, not wording.

Goldens are recorded by a real Bedrock run (scripts/record_goldens.py, Phase 2
last mile) and committed deliberately. Until they exist these tests skip, so
the suite stays green offline; once recorded they enforce the intended
verdict classes from PLAN.md.
"""

import json
from pathlib import Path

import pytest

from verdict import validate_verdict

GOLDEN_DIR = Path(__file__).parent / "golden"

# "actions" = the proportionate superset a verdict may propose;
# "must_include_one_of" = the instance/credential-scoped containment the
# PLAN's intended outcome centres on.
EXPECTED = {
    "ssh-bruteforce": {
        "verdict": "true_positive",
        "actions": {"isolate_instance_sg", "block_ip_nacl"},
        "must_include_one_of": {"isolate_instance_sg"},
    },
    "crypto-mining": {
        "verdict": "true_positive",
        "actions": {
            "stop_instance",
            "isolate_instance_sg",
            "revoke_iam_sessions",
            "quarantine_snapshot",
        },
        "must_include_one_of": {"stop_instance", "isolate_instance_sg"},
        "severity": {"critical", "high"},
    },
    "tor-recon": {
        "verdict": "needs_human",
        "actions": set(),
    },
}


def golden_path(stem: str) -> Path:
    return GOLDEN_DIR / f"{stem}.verdict.json"


@pytest.mark.parametrize("stem", sorted(EXPECTED))
def test_golden_verdict_class(stem):
    path = golden_path(stem)
    # Goldens are committed: a missing one is a regression, not a skip
    # (PR #2 review finding).
    assert path.exists(), f"golden missing: {path.name} — re-record with scripts/record_goldens.py"

    verdict = json.loads(path.read_text())
    expected = EXPECTED[stem]

    validate_verdict(verdict)
    assert verdict["verdict"] == expected["verdict"]

    proposed = {a["action"] for a in verdict["proposed_actions"]}
    if expected["actions"]:
        assert proposed, f"{stem}: expected a containment proposal, got none"
        assert proposed <= expected["actions"], f"disproportionate proposal(s): {proposed}"
        must = expected.get("must_include_one_of")
        if must:
            assert proposed & must, f"{stem}: none of {must} proposed, got {proposed}"
    else:
        assert not proposed, f"{stem}: expected no proposals, got {proposed}"

    if "severity" in expected:
        assert verdict["severity_assessment"] in expected["severity"]

    if verdict["verdict"] == "needs_human":
        assert verdict["escalate_to_human"] is True
