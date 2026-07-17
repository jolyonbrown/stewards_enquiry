"""The triage loop: a Strands agent over the four tools, verdicts validated
or failed closed.

The model is injectable for tests; the default is Claude on Bedrock with the
model id read from BEDROCK_MODEL_ID — never hardcoded. Discover a current
Claude Sonnet cross-region inference profile with:

    aws bedrock list-inference-profiles --region "$AWS_REGION"
"""

import json
import logging
import os
from typing import Any

from strands import Agent, tool

import telemetry
from prompts import SYSTEM_PROMPT, TASK_PROMPT
from tools import get_finding, lookup_ip, propose_containment, query_cloudtrail
from verdict import extract_json_object, fail_closed_verdict, validate_verdict

logger = logging.getLogger("stewards_enquiry.triage")

MODEL_ID_ENV = "BEDROCK_MODEL_ID"


def _check_verdict_against_trace(verdict: dict, trace: list[dict]) -> None:
    """The verdict must be grounded in what the tools actually did and said.

    A model can emit a schema-valid verdict citing tools it never called,
    a finding it never fetched, or proposals that never went through
    propose_containment (and so never reached proposals.jsonl). Each of
    those is a fabrication, and fabrications fail closed (PR #2 review).
    """
    calls_by_tool: dict[str, list] = {}
    for entry in trace:
        calls_by_tool.setdefault(entry["tool"], []).append(entry["result"])

    fetched_ids = {f.get("id") for f in calls_by_tool.get("get_finding", [])}
    if not fetched_ids:
        raise ValueError("verdict produced without ever calling get_finding")
    if verdict["finding_id"] not in fetched_ids:
        raise ValueError(
            f"verdict finding_id {verdict['finding_id']!r} does not match any fetched finding"
        )

    cited = {e["tool"] for e in verdict["evidence"]}
    uncalled = cited - set(calls_by_tool)
    if uncalled:
        raise ValueError(f"evidence cites tool(s) never called: {sorted(uncalled)}")

    recorded = calls_by_tool.get("propose_containment", [])
    for action in verdict["proposed_actions"]:
        if action not in recorded:
            raise ValueError(
                f"proposed action {action.get('action')!r} on {action.get('target')!r} "
                "was never routed through propose_containment"
            )


def default_model() -> Any:
    """Claude on Bedrock; model id from the environment (see module docstring)."""
    from strands.models.bedrock import BedrockModel  # deferred: needs AWS config

    model_id = os.environ.get(MODEL_ID_ENV)
    if not model_id:
        raise RuntimeError(
            f"{MODEL_ID_ENV} is not set. Set it to a current Claude inference "
            "profile id (aws bedrock list-inference-profiles)."
        )
    return BedrockModel(model_id=model_id)


def build_agent(model: Any) -> Agent:
    """One fresh agent per triage — no conversation state crosses findings."""
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            tool(get_finding),
            tool(lookup_ip),
            tool(query_cloudtrail),
            tool(propose_containment),
        ],
    )


def run_triage(finding_id: str, model: Any = None) -> dict:
    """Triage one finding and return a schema-valid verdict, whatever happens.

    Any failure — model unreachable, unparseable output, schema or policy
    violation, verdict not grounded in the tool trace — produces a
    fail-closed needs_human verdict (invariant 3), never an exception and
    never free text.
    """
    telemetry.begin_trace()
    try:
        agent = build_agent(model if model is not None else default_model())
        result = agent(TASK_PROMPT.format(finding_id=finding_id))
        verdict = validate_verdict(extract_json_object(str(result)))
        _check_verdict_against_trace(verdict, telemetry.get_trace())
    except Exception as exc:
        logger.warning("triage failed closed for %r: %s", finding_id, exc)
        verdict = fail_closed_verdict(finding_id, reason=f"{type(exc).__name__}: {exc}")
    finally:
        telemetry.end_trace()

    logger.info(
        json.dumps(
            {
                "event": "verdict",
                "finding_id": verdict["finding_id"],
                "verdict": verdict["verdict"],
                "confidence": verdict["confidence"],
                "escalate_to_human": verdict["escalate_to_human"],
                "proposed_actions": len(verdict["proposed_actions"]),
            },
            separators=(",", ":"),
        )
    )
    return verdict
