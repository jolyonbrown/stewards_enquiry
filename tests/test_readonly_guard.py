"""Invariant 1 wired into the test run: the read-only grep must pass."""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_codebase_contains_no_mutating_aws_calls():
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "verify_readonly.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"\n{result.stdout}{result.stderr}"
