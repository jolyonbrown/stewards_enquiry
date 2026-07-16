"""verdict module: schema validation, JSON extraction, and the fail-closed path."""

import jsonschema
import pytest

from verdict import extract_json_object, fail_closed_verdict, validate_verdict

VALID_VERDICT = {
    "finding_id": "f-ssh-bruteforce-0001",
    "verdict": "true_positive",
    "confidence": 0.9,
    "severity_assessment": "medium",
    "summary": "The instance received a sustained SSH brute-force from a known-malicious IP.",
    "evidence": [
        {"tool": "get_finding", "observation": "41 inbound SSH attempts from 203.0.113.42"},
        {"tool": "lookup_ip", "observation": "203.0.113.42 is malicious (score 97)"},
    ],
    "proposed_actions": [
        {
            "action": "isolate_instance_sg",
            "target": "sg-0aa11bb22cc33dd44",
            "justification": "Sustained brute force from a known-malicious IP",
            "risk_if_wrong": "Legitimate SSH admin access to web-03 is blocked",
            "requires_approval": True,
            "status": "pending_approval",
        }
    ],
    "escalate_to_human": False,
}


def test_valid_verdict_passes():
    assert validate_verdict(VALID_VERDICT) is VALID_VERDICT


@pytest.mark.parametrize(
    "mutation",
    [
        {"verdict": "guilty"},  # not in enum
        {"confidence": 1.5},  # out of range
        {"proposed_actions": [{"action": "no_action"}]},  # missing required fields
        {"extra_field": "x"},  # additionalProperties: false
        {"evidence": []},  # minItems: 1
    ],
)
def test_invalid_verdicts_are_rejected(mutation):
    with pytest.raises(jsonschema.ValidationError):
        validate_verdict({**VALID_VERDICT, **mutation})


def test_proposal_status_other_than_pending_approval_is_schema_invalid():
    action = dict(VALID_VERDICT["proposed_actions"][0], status="approved")
    with pytest.raises(jsonschema.ValidationError):
        validate_verdict({**VALID_VERDICT, "proposed_actions": [action]})


def test_extract_plain_json():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_from_fenced_and_prosed_text():
    text = 'Here is my verdict:\n```json\n{"a": {"b": 2}}\n```\nDone.'
    assert extract_json_object(text) == {"a": {"b": 2}}


@pytest.mark.parametrize("text", ["no json here", "[1, 2, 3]", ""])
def test_extract_rejects_non_objects(text):
    with pytest.raises(ValueError):
        extract_json_object(text)


def test_fail_closed_verdict_is_schema_valid_needs_human():
    verdict = fail_closed_verdict("f-x-1", reason="model unreachable")
    validate_verdict(verdict)
    assert verdict["verdict"] == "needs_human"
    assert verdict["escalate_to_human"] is True
    assert verdict["proposed_actions"] == []
    assert "model unreachable" in verdict["summary"]


def test_fail_closed_verdict_survives_hostile_inputs():
    verdict = fail_closed_verdict("  ", reason="x" * 2000)
    validate_verdict(verdict)
    assert verdict["finding_id"] == "unknown"
    assert len(verdict["summary"]) <= 800
