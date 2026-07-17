#!/usr/bin/env bash
# End-to-end proof, one command:
#   offline suite -> fresh package + deploy (new immutable runtime version)
#   -> remote triage of all three bundled findings -> verdict classes
#   checked against the committed goldens.
#
# Needs: AWS credentials (e.g. AWS_PROFILE=limilo), region with AgentCore
# support configured in agentcore/aws-targets.json. Run from anywhere:
#
#   AWS_PROFILE=limilo AWS_REGION=eu-west-2 bash scripts/e2e_remote.sh
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
    agentcore invoke "{\"finding_id\": \"$finding\"}" | tee "$OUT_DIR/$finding.out"
    echo
done

echo "== 4/4 remote verdict classes vs committed goldens =="
uv run python - "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
failures = []
for stem in ("ssh-bruteforce", "crypto-mining", "tor-recon"):
    want = json.loads(Path(f"tests/golden/{stem}.verdict.json").read_text())["verdict"]
    text = (out_dir / f"{stem}.out").read_text()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        print(f"{stem}: NO JSON IN RESPONSE")
        failures.append(stem)
        continue
    verdict = json.loads(text[start : end + 1])
    # invoke output may wrap the verdict in a response envelope
    while isinstance(verdict, dict) and "verdict" not in verdict and len(verdict) == 1:
        verdict = next(iter(verdict.values()))
    got = verdict.get("verdict")
    ok = got == want
    if got == "needs_human":
        ok = ok and verdict.get("escalate_to_human") is True and not verdict.get("proposed_actions")
    print(f"{stem}: remote={got} golden={want} -> {'OK' if ok else 'MISMATCH'}")
    if not ok:
        failures.append(stem)
sys.exit(1 if failures else 0)
PY

echo
echo "E2E PASS — remote behaviour matches the local goldens."
