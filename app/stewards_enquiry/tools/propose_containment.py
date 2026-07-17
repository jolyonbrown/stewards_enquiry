"""propose_containment — a no-op by construction. Invariant 2: propose, never act.

Appends a structured proposal to proposals.jsonl and returns it. There is no
code path that executes a containment action: ``status`` and
``requires_approval`` are hardcoded constants with no parameter to override
them, and ``action`` must come from the verdict schema's enum. Live mode
changes nothing, by design.

The returned dict is shaped exactly like a ``proposed_actions`` item in
schemas/verdict.schema.json so Phase 2 can embed it verbatim; the JSONL
record carries two extra audit fields (proposal_id, created_at).
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from telemetry import traced

PROPOSALS_PATH_ENV = "STEWARD_PROPOSALS_PATH"

# Mirrors the action enum in schemas/verdict.schema.json; a unit test keeps
# the two in sync.
ALLOWED_ACTIONS = frozenset(
    {
        "isolate_instance_sg",
        "stop_instance",
        "revoke_iam_sessions",
        "disable_access_key",
        "block_ip_nacl",
        "quarantine_snapshot",
        "no_action",
    }
)

_STATUS = "pending_approval"  # the only status this module can ever emit


@traced
def propose_containment(action: str, target: str, justification: str, risk_if_wrong: str) -> dict:
    """Record a containment proposal awaiting human approval. Executes nothing."""
    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"action {action!r} is not in the verdict schema enum: {sorted(ALLOWED_ACTIONS)}"
        )
    for name, value in (
        ("target", target),
        ("justification", justification),
        ("risk_if_wrong", risk_if_wrong),
    ):
        if not value or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    # Mirror the schema's maxLength so no invalid proposal ever reaches disk.
    for name, value in (("justification", justification), ("risk_if_wrong", risk_if_wrong)):
        if len(value) > 400:
            raise ValueError(f"{name} exceeds the schema's 400-character limit ({len(value)})")

    proposal = {
        "action": action,
        "target": target,
        "justification": justification,
        "risk_if_wrong": risk_if_wrong,
        "requires_approval": True,
        "status": _STATUS,
    }
    record = {
        "proposal_id": hashlib.sha256(
            json.dumps([action, target, justification, risk_if_wrong]).encode()
        ).hexdigest()[:12],
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **proposal,
    }
    path = Path(os.environ.get(PROPOSALS_PATH_ENV, "proposals.jsonl"))
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")
    return proposal
