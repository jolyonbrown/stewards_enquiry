"""Record golden verdicts: the three fixture findings through a real model.

Needs AWS credentials with Bedrock model access and BEDROCK_MODEL_ID set.
Run from the repo root:

    uv run python scripts/record_goldens.py

Commit the resulting tests/golden/*.verdict.json deliberately (per CLAUDE.md,
with a commit message explaining why) — never silently.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "app" / "stewards_enquiry"))

from triage import run_triage  # noqa: E402

GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
FINDINGS = ("ssh-bruteforce", "crypto-mining", "tor-recon")


def main() -> int:
    GOLDEN_DIR.mkdir(exist_ok=True)
    failures = 0
    for stem in FINDINGS:
        print(f"→ triaging {stem} ...")
        verdict = run_triage(stem)
        if verdict["summary"].startswith("Automated triage could not produce"):
            print(f"  FAIL-CLOSED — not a real verdict, refusing to record: {verdict['summary']}")
            failures += 1
            continue
        path = GOLDEN_DIR / f"{stem}.verdict.json"
        path.write_text(json.dumps(verdict, indent=2) + "\n")
        print(f"  {verdict['verdict']} (confidence {verdict['confidence']}) → {path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
