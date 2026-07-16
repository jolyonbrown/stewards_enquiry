"""Invariant 1 wired into the test run — and regression-tested against bypasses.

The guard is a denylist, so its value depends on actually catching the call
shapes reviewers have shown it missing. Every probe below was a real bypass
found in review (PR #1: gpt-5.6 found terminate/upload_file/copy_object/
batch_write_item/`aws s3 cp`; opus-4.8 found publish/invoke/copy_snapshot).
"""

import subprocess
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_readonly.sh"


def run_guard() -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, check=False)


def test_codebase_contains_no_mutating_aws_calls():
    result = run_guard()
    assert result.returncode == 0, f"\n{result.stdout}{result.stderr}"


PY_PROBES = [
    'client.stop_instances(InstanceIds=["i-1"])',
    "instance.terminate()",
    'sns.publish(TopicArn="arn", Message="m")',
    'lam.invoke(FunctionName="f")',
    'ec2.copy_snapshot(SourceSnapshotId="snap-1")',
    's3.upload_file("local", "bucket", "key")',
    "ddb.batch_write_item(RequestItems={})",
    'iam.set_default_policy_version(PolicyArn="a", VersionId="v1")',
    'client.put_object(Bucket="b", Key="k")',
]

SH_PROBES = [
    "aws s3 cp secrets.txt s3://bucket/",
    "aws ec2 terminate-instances --instance-ids i-1",
    "aws iam create-access-key --user-name x",
    "aws sns publish-batch --topic-arn arn",
]


def plant_and_run(content: str, suffix: str) -> subprocess.CompletedProcess:
    probe = REPO_ROOT / "app" / "stewards_enquiry" / f"guard_probe_{uuid.uuid4().hex}{suffix}"
    probe.write_text(content + "\n")
    try:
        return run_guard()
    finally:
        probe.unlink()


@pytest.mark.parametrize("probe", PY_PROBES)
def test_guard_catches_mutating_python_calls(probe):
    result = plant_and_run(probe, ".py")
    assert result.returncode == 1, f"bypass not caught: {probe}\n{result.stdout}"


@pytest.mark.parametrize("probe", SH_PROBES)
def test_guard_catches_mutating_cli_calls(probe):
    result = plant_and_run(probe, ".sh")
    assert result.returncode == 1, f"bypass not caught: {probe}\n{result.stdout}"


def test_guard_reports_the_offending_line():
    result = plant_and_run('client.stop_instances(InstanceIds=["i-1"])', ".py")
    assert "stop_instances" in result.stdout
