#!/usr/bin/env bash
# Invariant 1 — read-only, everywhere — a CI tripwire behind the primary
# control (the read-only IAM execution role).
#
# Denylist grep for AWS-mutating call shapes in OUR code. Honest scope note:
# a denylist cannot prove the absence of every mutating API; it catches the
# call shapes that could plausibly appear here — control-plane mutation,
# data-plane writes, messaging, and code execution — and it is regression-
# tested against known bypasses in tests/test_readonly_guard.py. Extend the
# verb lists when a new AWS surface enters the codebase.
# Allowed API verbs remain: Get*, List*, Describe*, Lookup*.
#
# Scope: every tracked or untracked-but-not-ignored file — vendored code
# (.venv, node_modules) is gitignored, ours is not.
set -euo pipefail

cd "$(dirname "$0")/.."

# boto3 snake_case methods, e.g. .stop_instances( .batch_write_item( .set_topic_attributes(
SNAKE='create|delete|put|update|modify|terminate|stop|start|reboot|attach|detach|revoke|authorize|disable|enable|associate|disassociate|cancel|reject|accept|tag|untag|run|register|deregister|replace|release|allocate|assign|unassign|purchase|request|restore|reset|rotate|send|admin|upload|copy|import|export|invoke|publish|grant|set|add|remove|batch'
# boto3 resource-object bare methods, e.g. instance.terminate( bucket.upload(
# ("run"/"send"/"update"/"add" stay snake-only: subprocess.run, generator.send,
# dict.update, set.add are legitimate Python)
BARE='terminate|stop|start|reboot|delete|create|put|copy|upload|publish|invoke'
PY_PATTERN="\.((${SNAKE})_[a-z0-9_]+|(${BARE}))\("

# aws CLI kebab-case subcommands plus the s3 data-plane shorthands
CLI_KEBAB='create|delete|put|update|modify|terminate|stop|start|reboot|attach|detach|revoke|authorize|disable|enable|associate|disassociate|cancel|register|deregister|import|export|invoke|publish|send|upload|copy|tag|untag|run|grant|set|add|remove'
SH_PATTERN="aws +s3 +(cp|mv|sync|rm|rb|mb)([^a-z-]|$)|aws +[a-z0-9-]+ +(${CLI_KEBAB})-"

# The guard script and its regression tests necessarily contain the very
# patterns they hunt, so they are the two (and only two) exclusions.
list_files() {
    git ls-files --cached --others --exclude-standard -- "$1" \
        | grep -vE '^(scripts/verify_readonly\.sh|tests/test_readonly_guard\.py)$' || true
}

status=0

py_files=$(list_files '*.py')
if [ -n "$py_files" ]; then
    hits=$(echo "$py_files" | xargs -d '\n' grep -En "$PY_PATTERN" 2>/dev/null || true)
    if [ -n "$hits" ]; then
        echo "FAIL: mutating AWS-style Python call(s) found:"
        echo "$hits"
        status=1
    fi
fi

sh_files=$(list_files '*.sh')
if [ -n "$sh_files" ]; then
    hits=$(echo "$sh_files" | xargs -d '\n' grep -En "$SH_PATTERN" 2>/dev/null || true)
    if [ -n "$hits" ]; then
        echo "FAIL: mutating aws CLI call(s) found:"
        echo "$hits"
        status=1
    fi
fi

if [ "$status" -eq 0 ]; then
    echo "OK: no mutating AWS call shapes found (allowed verbs: Get*, List*, Describe*, Lookup*)"
fi
exit "$status"
