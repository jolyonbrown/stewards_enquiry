"""Verdict validation — invariant 3: verdicts validate or fail closed.

A candidate verdict either validates against schemas/verdict.schema.json or
is replaced by a minimal ``needs_human`` verdict. No code path returns free
text to the caller.
"""

import json
from functools import cache
from pathlib import Path

import jsonschema


@cache
def verdict_schema() -> dict:
    """Load the verdict schema: works from the repo and from a deployed CodeZip."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "schemas" / "verdict.schema.json"
        if candidate.is_file():
            return json.loads(candidate.read_text())
    raise FileNotFoundError(f"No schemas/verdict.schema.json found above {Path(__file__)}")


def validate_verdict(candidate: dict) -> dict:
    """Return `candidate` if it validates; raise jsonschema.ValidationError if not."""
    jsonschema.validate(candidate, verdict_schema())
    return candidate


def extract_json_object(text: str) -> dict:
    """Pull the outermost JSON object from model text (tolerates fences/prose)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("model output JSON is not an object")
    return parsed


def fail_closed_verdict(finding_id: str, reason: str) -> dict:
    """Minimal schema-valid verdict for when triage goes wrong, in any way.

    The evidence entry is a placeholder required by the schema (min 1 item,
    tool from a fixed enum); its observation states plainly that this is a
    fail-closed verdict, not an investigation result.
    """
    verdict = {
        "finding_id": finding_id.strip() or "unknown",
        "verdict": "needs_human",
        "confidence": 0.0,
        "severity_assessment": "medium",
        "summary": (
            "Automated triage could not produce a valid verdict, so this finding "
            f"needs human review. Reason: {reason}"
        )[:800],
        "evidence": [
            {
                "tool": "get_finding",
                "observation": ("Fail-closed verdict; triage output was discarded. " + reason)[
                    :400
                ],
            }
        ],
        "proposed_actions": [],
        "escalate_to_human": True,
    }
    # A fail-closed verdict that does not itself validate is a bug, not a
    # condition to handle — let it raise.
    return validate_verdict(verdict)
