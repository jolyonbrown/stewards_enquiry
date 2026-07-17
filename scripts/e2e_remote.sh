#!/usr/bin/env bash
# End-to-end proof, one command:
#   offline suite -> fresh package + deploy (new immutable runtime version)
#   -> remote triage of all three bundled findings -> each remote verdict
#   schema+policy validated, checked against the committed golden's
#   finding_id and the suite's expected verdict class / action policy.
#
# A fail-closed response, a swapped response, or a disproportionate proposal
# set FAILS the run (PR #3 review: class-only comparison was spoofable).
#
# Needs: AWS credentials (e.g. AWS_PROFILE=<your-profile>), region with AgentCore
# support configured in agentcore/aws-targets.json. Run from anywhere:
#
#   AWS_PROFILE=<your-profile> AWS_REGION=eu-west-2 bash scripts/e2e_remote.sh
#
# Skip the redeploy (invoke-only, e.g. mid-demo) with: --no-deploy
set -euo pipefail

cd "$(dirname "$0")/.."
OUT_DIR="${TMPDIR:-/tmp}/steward-e2e"
mkdir -p "$OUT_DIR"

echo "== 1/4 offline suite (the governance guarantees travel with the deploy) =="
uv run pytest -q

if [ "${1:-}" = "--no-deploy" ]; then
    echo "== 2/4 deploy skipped (--no-deploy) =="
else
    echo "== 2/4 fresh package + deploy (creates a new immutable runtime version) =="
    agentcore deploy -y
fi

echo "== 3/4 remote triage of the three bundled findings =="
for finding in ssh-bruteforce crypto-mining tor-recon; do
    echo "-- invoking for $finding"
    agentcore invoke --json "{\"finding_id\": \"$finding\"}" > "$OUT_DIR/$finding.json"
done

echo "== 4/4 remote verdicts vs goldens + suite policy =="
uv run python - "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, "app/stewards_enquiry")
sys.path.insert(0, "tests")
from test_golden_verdicts import EXPECTED  # the same policy the suite enforces
from verdict import validate_verdict

out_dir = Path(sys.argv[1])
failures = []
for stem, policy in EXPECTED.items():
    label = f"{stem}:"
    try:
        envelope = json.loads((out_dir / f"{stem}.json").read_text())
        assert envelope.get("success") is True, "invoke envelope reported failure"
        remote = json.loads(envelope["response"])
        validate_verdict(remote)  # full schema + cross-field policy

        golden = json.loads(Path(f"tests/golden/{stem}.verdict.json").read_text())
        problems = []
        if remote["summary"].startswith("Automated triage could not produce"):
            problems.append("fail-closed verdict, not a real triage")
        if remote["finding_id"] != golden["finding_id"]:
            problems.append(f"finding_id {remote['finding_id']!r} != {golden['finding_id']!r}")
        if remote["verdict"] != policy["verdict"]:
            problems.append(f"verdict {remote['verdict']!r}, expected {policy['verdict']!r}")
        if "severity" in policy and remote["severity_assessment"] not in policy["severity"]:
            problems.append(f"severity {remote['severity_assessment']!r} outside {policy['severity']}")

        proposed = {a["action"] for a in remote["proposed_actions"]}
        if policy["actions"]:
            if not proposed:
                problems.append("expected a containment proposal, got none")
            elif not proposed <= policy["actions"]:
                problems.append(f"disproportionate proposals {sorted(proposed)}")
            must = policy.get("must_include_one_of")
            if must and not proposed & must:
                problems.append(f"none of {sorted(must)} proposed")
        elif proposed:
            problems.append(f"expected no proposals, got {sorted(proposed)}")

        if problems:
            print(f"{label} FAIL — {'; '.join(problems)}")
            failures.append(stem)
        else:
            print(
                f"{label} remote={remote['verdict']} "
                f"(confidence {remote['confidence']}) matches golden + policy -> OK"
            )
    except Exception as exc:
        print(f"{label} FAIL — {type(exc).__name__}: {exc}")
        failures.append(stem)

sys.exit(1 if failures else 0)
PY

echo
echo "E2E PASS — remote behaviour matches the local goldens and suite policy."
