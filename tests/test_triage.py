"""run_triage: valid, trace-grounded model output passes; everything else fails closed.

The agent is faked at the build_agent seam. Since PR #2 review, a verdict
must also be grounded in the tool trace: the fake agent therefore actually
calls the (real, fixture-backed) tools the way the model would, and the
negative tests prove fabrications fail closed.
"""

import json
import logging

import pytest
from test_verdict import VALID_VERDICT

import triage
from tools import get_finding, lookup_ip, propose_containment
from triage import run_triage

PROPOSAL_ARGS = {
    "action": "isolate_instance_sg",
    "target": "sg-0aa11bb22cc33dd44",
    "justification": "Sustained brute force from a known-malicious IP",
    "risk_if_wrong": "Legitimate SSH admin access to web-03 is blocked",
}


@pytest.fixture(autouse=True)
def isolated_proposals_file(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_PROPOSALS_PATH", str(tmp_path / "proposals.jsonl"))


class FakeAgent:
    """Replays a canned reply after optionally investigating like the model would."""

    def __init__(self, reply, investigate=(), proposals=()):
        self.reply = reply
        self.investigate = investigate
        self.proposals = proposals

    def __call__(self, prompt):
        if isinstance(self.reply, Exception):
            raise self.reply
        for fn, args in self.investigate:
            fn(*args)
        for kwargs in self.proposals:
            propose_containment(**kwargs)
        return self.reply


INVESTIGATION = ((get_finding, ("ssh-bruteforce",)), (lookup_ip, ("203.0.113.42",)))


@pytest.fixture
def agent(monkeypatch):
    def install(reply, investigate=INVESTIGATION, proposals=(PROPOSAL_ARGS,)):
        fake = FakeAgent(reply, investigate, proposals)
        monkeypatch.setattr(triage, "build_agent", lambda model: fake)

    return install


def test_grounded_valid_output_becomes_the_verdict(agent):
    agent(json.dumps(VALID_VERDICT))
    assert run_triage("ssh-bruteforce", model=object()) == VALID_VERDICT


def test_fenced_model_output_is_tolerated(agent):
    agent(f"My verdict:\n```json\n{json.dumps(VALID_VERDICT)}\n```")
    assert run_triage("ssh-bruteforce", model=object()) == VALID_VERDICT


def test_unparseable_output_fails_closed(agent):
    agent("I could not decide, sorry.")
    verdict = run_triage("ssh-bruteforce", model=object())
    assert verdict["verdict"] == "needs_human"
    assert verdict["escalate_to_human"] is True


def test_schema_invalid_output_fails_closed(agent):
    agent(json.dumps({**VALID_VERDICT, "verdict": "guilty"}))
    assert run_triage("ssh-bruteforce", model=object())["verdict"] == "needs_human"


def test_agent_exception_fails_closed(agent):
    agent(RuntimeError("bedrock unreachable"))
    verdict = run_triage("ssh-bruteforce", model=object())
    assert verdict["verdict"] == "needs_human"
    assert "bedrock unreachable" in verdict["summary"]


def test_missing_model_id_fails_closed_offline(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    verdict = run_triage("ssh-bruteforce")  # no model injected, no env set
    assert verdict["verdict"] == "needs_human"
    assert "BEDROCK_MODEL_ID" in verdict["summary"]


# --- trace grounding (PR #2 review: fabrications must fail closed) ---


def test_verdict_without_any_get_finding_call_fails_closed(agent):
    agent(json.dumps(VALID_VERDICT), investigate=((lookup_ip, ("203.0.113.42",)),))
    verdict = run_triage("ssh-bruteforce", model=object())
    assert verdict["verdict"] == "needs_human"
    assert "get_finding" in verdict["summary"]


def test_finding_id_not_matching_fetched_finding_fails_closed(agent):
    agent(
        json.dumps(VALID_VERDICT),  # claims f-ssh-bruteforce-0001
        investigate=((get_finding, ("tor-recon",)), (lookup_ip, ("203.0.113.42",))),
    )
    verdict = run_triage("tor-recon", model=object())
    assert verdict["verdict"] == "needs_human"
    assert "does not match any fetched finding" in verdict["summary"]


def test_evidence_citing_uncalled_tool_fails_closed(agent):
    agent(json.dumps(VALID_VERDICT), investigate=((get_finding, ("ssh-bruteforce",)),))
    verdict = run_triage("ssh-bruteforce", model=object())
    assert verdict["verdict"] == "needs_human"
    assert "never called" in verdict["summary"]


def test_fabricated_proposal_fails_closed(agent):
    agent(json.dumps(VALID_VERDICT), proposals=())  # claims a proposal it never made
    verdict = run_triage("ssh-bruteforce", model=object())
    assert verdict["verdict"] == "needs_human"
    assert "propose_containment" in verdict["summary"]


def test_every_triage_emits_a_verdict_log_line(agent, caplog):
    agent(json.dumps(VALID_VERDICT))
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
