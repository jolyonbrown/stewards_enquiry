"""Steward's Enquiry — AgentCore Runtime entrypoint.

POST /invocations takes a GuardDuty finding reference and returns a
schema-valid verdict; /ping comes from the SDK wrapper. Accepted payloads:

    {"finding_id": "ssh-bruteforce"}          # direct (curl, remote invoke)
    {"prompt": "ssh-bruteforce"}              # agentcore dev/invoke wrapper
    {"prompt": "{\\"finding_id\\": \\"...\\"}"}   # wrapper around JSON text

A payload with no usable finding id gets a fail-closed needs_human verdict,
not an error (invariant 3: no free-text failure modes).
"""

import json
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from telemetry import configure_logging
from triage import run_triage
from verdict import fail_closed_verdict

configure_logging()
app = BedrockAgentCoreApp()


def extract_finding_id(payload: dict[str, Any]) -> str | None:
    """Find a finding id in the payload shapes we accept; None if absent."""
    finding_id = payload.get("finding_id")
    if isinstance(finding_id, str) and finding_id.strip():
        return finding_id.strip()

    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    text = prompt.strip()
    try:
        inner = json.loads(text)
    except json.JSONDecodeError:
        return text  # a bare finding id, e.g. "ssh-bruteforce"
    if isinstance(inner, dict):
        inner_id = inner.get("finding_id")
        if isinstance(inner_id, str) and inner_id.strip():
            return inner_id.strip()
    if isinstance(inner, str) and inner.strip():
        return inner.strip()  # a JSON-quoted finding id
    return None


@app.entrypoint
def invoke(payload: dict[str, Any], context: Any) -> dict[str, Any]:
    finding_id = extract_finding_id(payload or {})
    if finding_id is None:
        return fail_closed_verdict(
            "unknown",
            reason="no finding id in payload; expected {'finding_id': '<id>'} "
            "or {'prompt': '<id>'}",
        )
    return run_triage(finding_id)


if __name__ == "__main__":
    app.run()
