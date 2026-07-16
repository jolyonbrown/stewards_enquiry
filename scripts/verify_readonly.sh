#!/usr/bin/env bash
# Invariant 1 — read-only, everywhere — enforced, not asserted.
#
# Fails if the codebase contains any AWS call that could create, modify, or
# delete anything. Allowed API verbs: Get*, List*, Describe*, Lookup*.
# Checks two shapes:
#   1. boto3-style snake_case method calls in Python (e.g. .stop_instances()
#   2. aws-CLI kebab-case subcommands in shell scripts (e.g. aws ec2 stop-instances)
#
# Run standalone or via tests/test_readonly_guard.py — pytest fails on any hit.
set -euo pipefail

cd "$(dirname "$0")/.."

MUTATING_VERBS='create|delete|put|update|modify|terminate|stop|start|reboot|attach|detach|revoke|authorize|disable|enable|associate|disassociate|cancel|reject|accept|tag|untag|run|register|deregister|replace|release|allocate|assign|unassign|purchase|request|restore|reset|rotate|send|admin'

PY_PATTERN="\.(${MUTATING_VERBS})_[a-z0-9_]+\("
SH_PATTERN="aws +[a-z0-9-]+ +(${MUTATING_VERBS})-"

# Our code only — vendored dependencies are governed by IAM, not this grep.
EXCLUDES='--exclude-dir=.venv --exclude-dir=site-packages --exclude-dir=node_modules --exclude-dir=__pycache__'

status=0

py_hits=$(grep -rEn $EXCLUDES --include='*.py' "$PY_PATTERN" app tests scripts 2>/dev/null || true)
if [ -n "$py_hits" ]; then
    echo "FAIL: mutating boto3-style call(s) found:"
    echo "$py_hits"
    status=1
fi

sh_hits=$(grep -rEn $EXCLUDES --include='*.sh' --exclude='verify_readonly.sh' "$SH_PATTERN" app tests scripts 2>/dev/null || true)
if [ -n "$sh_hits" ]; then
    echo "FAIL: mutating aws CLI call(s) found:"
    echo "$sh_hits"
    status=1
fi

if [ "$status" -eq 0 ]; then
    echo "OK: no mutating AWS calls found (allowed verbs: Get*, List*, Describe*, Lookup*)"
fi
exit "$status"
