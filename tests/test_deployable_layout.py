"""The CodeZip ships codeLocation only — everything the agent reads at runtime
must physically live inside it (PR #1 review finding: fixtures at the repo
root would FileNotFoundError once deployed). Root-level fixtures/ and schemas/
are symlinks for humans; the real files live in the deployable directory.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def code_location() -> Path:
    config = json.loads((REPO_ROOT / "agentcore" / "agentcore.json").read_text())
    return REPO_ROOT / config["runtimes"][0]["codeLocation"]


def test_fixtures_live_inside_code_location():
    fixtures = code_location() / "fixtures"
    assert fixtures.is_dir() and not fixtures.is_symlink()
    assert sorted(p.stem for p in (fixtures / "findings").glob("*.json")) == [
        "crypto-mining",
        "ssh-bruteforce",
        "tor-recon",
    ]
    assert (fixtures / "ip_reputation.json").is_file()
    assert (fixtures / "cloudtrail_events.json").is_file()


def test_schema_lives_inside_code_location():
    schema = code_location() / "schemas" / "verdict.schema.json"
    assert schema.is_file() and not schema.is_symlink()
