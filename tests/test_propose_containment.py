"""propose_containment: invariant 2 as tests — it can only ever propose.

The load-bearing assertions: no input can produce a status other than
pending_approval, there is no parameter through which a caller could change
that, and the action enum cannot drift from the verdict schema.
"""

import inspect
import json
from pathlib import Path

import pytest

from tools import propose_containment
from tools.propose_containment import ALLOWED_ACTIONS

REPO_ROOT = Path(__file__).resolve().parent.parent

VALID_ARGS = {
    "target": "sg-0aa11bb22cc33dd44",
    "justification": "41 SSH brute-force attempts from a known-malicious IP",
    "risk_if_wrong": "Legitimate admin SSH access to web-03 is blocked",
}


@pytest.fixture(autouse=True)
def isolated_proposals_file(monkeypatch, tmp_path):
    path = tmp_path / "proposals.jsonl"
    monkeypatch.setenv("STEWARD_PROPOSALS_PATH", str(path))
    return path


@pytest.mark.parametrize("action", sorted(ALLOWED_ACTIONS))
def test_every_valid_action_is_pending_approval_and_requires_approval(action):
    proposal = propose_containment(action=action, **VALID_ARGS)
    assert proposal["status"] == "pending_approval"
    assert proposal["requires_approval"] is True


def test_no_parameter_exists_to_override_status_or_approval():
    params = inspect.signature(propose_containment).parameters
    assert set(params) == {"action", "target", "justification", "risk_if_wrong"}


def test_action_enum_matches_verdict_schema():
    schema = json.loads((REPO_ROOT / "schemas" / "verdict.schema.json").read_text())
    schema_actions = schema["properties"]["proposed_actions"]["items"]["properties"]["action"][
        "enum"
    ]
    assert set(schema_actions) == ALLOWED_ACTIONS


def test_return_value_is_shaped_like_a_schema_proposed_action():
    proposal = propose_containment(action="isolate_instance_sg", **VALID_ARGS)
    assert set(proposal) == {
        "action",
        "target",
        "justification",
        "risk_if_wrong",
        "requires_approval",
        "status",
    }


def test_appends_jsonl_record_with_audit_fields(isolated_proposals_file):
    propose_containment(action="isolate_instance_sg", **VALID_ARGS)
    propose_containment(action="stop_instance", **VALID_ARGS)

    lines = isolated_proposals_file.read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert record["status"] == "pending_approval"
        assert record["requires_approval"] is True
        assert record["proposal_id"]
        assert record["created_at"]


def test_unknown_action_is_rejected_and_writes_nothing(isolated_proposals_file):
    with pytest.raises(ValueError, match="not in the verdict schema enum"):
        propose_containment(action="execute_containment", **VALID_ARGS)
    assert not isolated_proposals_file.exists()


@pytest.mark.parametrize("field", ["target", "justification", "risk_if_wrong"])
def test_blank_fields_are_rejected(field):
    args = dict(VALID_ARGS, **{field: "  "})
    with pytest.raises(ValueError, match=field):
        propose_containment(action="no_action", **args)


def test_return_value_is_deterministic():
    first = propose_containment(action="no_action", **VALID_ARGS)
    second = propose_containment(action="no_action", **VALID_ARGS)
    assert first == second
