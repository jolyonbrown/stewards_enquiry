"""Entrypoint: payload shapes in, schema-valid verdict out, fail-closed on junk."""

import json

import pytest

import main
from main import extract_finding_id, invoke
from verdict import validate_verdict


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"finding_id": "ssh-bruteforce"}, "ssh-bruteforce"),
        ({"finding_id": "  f-x-1  "}, "f-x-1"),
        ({"prompt": "ssh-bruteforce"}, "ssh-bruteforce"),
        ({"prompt": '{"finding_id": "crypto-mining"}'}, "crypto-mining"),
        ({"prompt": '"tor-recon"'}, "tor-recon"),
        ({"prompt": json.dumps({"finding_id": "a"}), "finding_id": "b"}, "b"),
    ],
)
def test_accepted_payload_shapes(payload, expected):
    assert extract_finding_id(payload) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"finding_id": ""},
        {"finding_id": 42},
        {"prompt": "   "},
        {"prompt": "[1, 2]"},
        {"prompt": "42"},
        {"prompt": '{"other_key": "x"}'},
    ],
)
def test_unusable_payloads_yield_none(payload):
    assert extract_finding_id(payload) is None


def test_invoke_delegates_to_run_triage(monkeypatch):
    seen = {}

    def fake_run_triage(finding_id):
        seen["finding_id"] = finding_id
        return {"sentinel": True}

    monkeypatch.setattr(main, "run_triage", fake_run_triage)

    assert invoke({"finding_id": "ssh-bruteforce"}, None) == {"sentinel": True}
    assert seen["finding_id"] == "ssh-bruteforce"


def test_invoke_without_finding_id_fails_closed_with_valid_verdict():
    verdict = invoke({"prompt": "[]"}, None)
    validate_verdict(verdict)
    assert verdict["verdict"] == "needs_human"
    assert verdict["finding_id"] == "unknown"
    assert verdict["escalate_to_human"] is True


@pytest.mark.parametrize("payload", [[1, 2], [{"finding_id": "x"}], "foo", 42, True, None])
def test_non_dict_json_payloads_fail_closed_not_500(payload):
    """PR #2 review (both reviewers): a valid-JSON non-object body reached
    .get() and raised AttributeError, which the runtime turns into a
    free-text 500 — the exact failure mode invariant 3 forbids."""
    verdict = invoke(payload, None)
    validate_verdict(verdict)
    assert verdict["verdict"] == "needs_human"
    assert type(payload).__name__ in verdict["summary"]
