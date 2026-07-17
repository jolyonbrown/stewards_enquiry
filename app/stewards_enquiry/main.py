"""Steward's Enquiry — AgentCore Runtime entrypoint.

Phase 0: a canned response proving the /invocations + /ping contract works
offline with zero AWS credentials. The triage loop replaces this in Phase 2.
"""

from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from telemetry import configure_logging

configure_logging()
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict[str, Any], context: Any) -> dict[str, Any]:
    return {
        "agent": "stewards-enquiry",
        "status": "ok",
        "message": "Phase 0 canned response — triage loop arrives in Phase 2.",
        "received": payload,
    }


if __name__ == "__main__":
    app.run()
