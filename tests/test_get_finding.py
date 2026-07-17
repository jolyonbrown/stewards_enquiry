"""get_finding: fixture lookup by id or filename stem, deterministic, offline."""

import pytest

from tools import get_finding


def test_loads_by_filename_stem():
    finding = get_finding("ssh-bruteforce")
    assert finding["id"] == "f-ssh-bruteforce-0001"
    assert finding["type"] == "UnauthorizedAccess:EC2/SSHBruteForce"


def test_loads_by_finding_id():
    assert get_finding("f-ssh-bruteforce-0001") == get_finding("ssh-bruteforce")


@pytest.mark.parametrize("stem", ["ssh-bruteforce", "crypto-mining", "tor-recon"])
def test_all_bundled_findings_load(stem):
    finding = get_finding(stem)
    assert finding["id"]
    assert finding["type"]
    assert finding["severity"] > 0


def test_unknown_id_raises_with_known_findings_listed():
    with pytest.raises(ValueError, match="ssh-bruteforce"):
        get_finding("does-not-exist")


def test_deterministic():
    assert get_finding("crypto-mining") == get_finding("crypto-mining")


def test_live_mode_is_not_silently_fixture_backed(monkeypatch):
    monkeypatch.setenv("STEWARD_LIVE", "1")
    with pytest.raises(NotImplementedError):
        get_finding("ssh-bruteforce")
