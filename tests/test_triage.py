"""run_triage: valid model output passes through; everything else fails closed.

The agent is faked at the build_agent seam — these tests prove the loop's
contract (invariant 3) without a model. The real loop is exercised end-to-end
by the golden runs (needs Bedrock credentials).
"""

import json
import logging

import pytest
from test_verdict import VALID_VERDICT

import triage
from triage import run_triage


class FakeAgent:
    def __init__(self, reply):
        self.reply = reply

    def __call__(self, prompt):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture
def agent_replying(monkeypatch):
    def install(reply):
        monkeypatch.setattr(triage, "build_agent", lambda model: FakeAgent(reply))

    return install


def test_valid_model_output_becomes_the_verdict(agent_replying):
    agent_replying(json.dumps(VALID_VERDICT))
    assert run_triage("ssh-bruteforce", model=object()) == VALID_VERDICT


def test_fenced_model_output_is_tolerated(agent_replying):
    agent_replying(f"My verdict:\n```json\n{json.dumps(VALID_VERDICT)}\n```")
    assert run_triage("ssh-bruteforce", model=object()) == VALID_VERDICT


def test_unparseable_output_fails_closed(agent_replying):
    agent_replying("I could not decide, sorry.")
    verdict = run_triage("ssh-bruteforce", model=object())
    assert verdict["verdict"] == "needs_human"
    assert verdict["escalate_to_human"] is True


def test_schema_invalid_output_fails_closed(agent_replying):
    agent_replying(json.dumps({**VALID_VERDICT, "verdict": "guilty"}))
    verdict = run_triage("ssh-bruteforce", model=object())
    assert verdict["verdict"] == "needs_human"


def test_agent_exception_fails_closed(agent_replying):
    agent_replying(RuntimeError("bedrock unreachable"))
    verdict = run_triage("ssh-bruteforce", model=object())
    assert verdict["verdict"] == "needs_human"
    assert "bedrock unreachable" in verdict["summary"]


def test_missing_model_id_fails_closed_offline(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    verdict = run_triage("ssh-bruteforce")  # no model injected, no env set
    assert verdict["verdict"] == "needs_human"
    assert "BEDROCK_MODEL_ID" in verdict["summary"]


def test_every_triage_emits_a_verdict_log_line(agent_replying, caplog):
    agent_replying(json.dumps(VALID_VERDICT))
    with caplog.at_level(logging.INFO, logger="stewards_enquiry.triage"):
        run_triage("ssh-bruteforce", model=object())

    lines = [
        json.loads(r.message)
        for r in caplog.records
        if r.name == "stewards_enquiry.triage" and r.message.startswith("{")
    ]
    assert len(lines) == 1
    assert lines[0]["event"] == "verdict"
    assert lines[0]["verdict"] == "true_positive"
    assert lines[0]["proposed_actions"] == 1
