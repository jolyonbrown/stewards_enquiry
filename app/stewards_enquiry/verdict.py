"""Verdict validation — invariant 3: verdicts validate or fail closed.

A candidate verdict either validates against schemas/verdict.schema.json AND
the cross-field policy rules below, or is replaced by a minimal
``needs_human`` verdict. No code path returns free text to the caller.
"""

import json
import math
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


def _check_policy(verdict: dict) -> None:
    """Cross-field rules the JSON schema cannot express (PR #2 review finding).

    Schema-valid but policy-invalid verdicts must fail closed too: the schema
    knows field shapes, not the triage policy.
    """
    problems = []
    if not math.isfinite(verdict["confidence"]):
        problems.append("confidence must be a finite number")
    if verdict["verdict"] == "needs_human" and verdict["escalate_to_human"] is not True:
        problems.append("needs_human requires escalate_to_human: true")
    if verdict["verdict"] in ("needs_human", "false_positive") and verdict["proposed_actions"]:
        problems.append(f"a {verdict['verdict']} verdict must not carry containment proposals")
    if verdict["verdict"] in ("true_positive", "benign_true_positive"):
        tools_cited = {e["tool"] for e in verdict["evidence"]}
        if len(tools_cited) < 2:
            problems.append(
                "a true_positive verdict needs corroboration from at least two distinct tools"
            )
    if problems:
        raise jsonschema.ValidationError("; ".join(problems))


def validate_verdict(candidate: dict) -> dict:
    """Return `candidate` if schema- and policy-valid; raise ValidationError if not."""
    jsonschema.validate(candidate, verdict_schema())
    _check_policy(candidate)
    return candidate


def _reject_json_constant(name: str) -> None:
    # json.loads would otherwise admit NaN/Infinity, which sail through the
    # schema's numeric bounds (nan comparisons are all False).
    raise ValueError(f"non-standard JSON constant {name!r} in model output")


def extract_json_object(text: str) -> dict:
    """Parse the first-`{`-to-last-`}` slice of model text as a JSON object.

    Tolerates markdown fences and prose *outside* that slice. Prose containing
    braces around a valid object makes the slice unparseable — that is
    accepted and fails closed upstream; the prompt mandates JSON-only output.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    parsed = json.loads(text[start : end + 1], parse_constant=_reject_json_constant)
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
