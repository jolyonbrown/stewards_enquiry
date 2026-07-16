"""lookup_ip: fixture-backed reputation with _default fallback, never external."""

from tools import lookup_ip


def test_known_malicious_ip():
    result = lookup_ip("203.0.113.42")
    assert result["known"] is True
    assert result["reputation"] == "malicious"
    assert "ssh-bruteforce" in result["tags"]


def test_tor_exit_node():
    assert lookup_ip("198.51.100.77")["reputation"] == "tor-exit-node"


def test_miss_returns_default_entry_with_ip_echoed():
    result = lookup_ip("10.99.99.99")
    assert result == {
        "ip": "10.99.99.99",
        "known": False,
        "reputation": "unknown",
        "score": 0,
        "reports_90d": 0,
        "tags": [],
        "first_seen": None,
        "last_seen": None,
    }


def test_metadata_keys_are_not_reachable_as_ips():
    assert lookup_ip("_default")["known"] is False
    assert lookup_ip("_comment")["known"] is False


def test_whitespace_is_stripped():
    assert lookup_ip(" 203.0.113.42 ")["reputation"] == "malicious"


def test_deterministic():
    assert lookup_ip("203.0.113.42") == lookup_ip("203.0.113.42")
