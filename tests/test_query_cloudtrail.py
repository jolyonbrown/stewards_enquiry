"""query_cloudtrail: window filtering anchored at the principal's newest event."""

import json

import pytest

from tools import query_cloudtrail
from tools.query_cloudtrail import MAX_EVENTS


def test_default_24h_window_for_svc_scanner():
    events = query_cloudtrail("svc-scanner")
    # Newest event is 2026-07-13T07:58:19Z; 24h back excludes the two
    # scheduled 02:00 scans on the 12th and 11th.
    assert len(events) == 4
    assert all(e["eventTime"].startswith("2026-07-13") for e in events)


def test_wider_windows_pull_in_older_events():
    assert len(query_cloudtrail("svc-scanner", hours=48)) == 5
    assert len(query_cloudtrail("svc-scanner", hours=72)) == 6


def test_events_are_newest_first():
    events = query_cloudtrail("svc-scanner", hours=72)
    times = [e["eventTime"] for e in events]
    assert times == sorted(times, reverse=True)


def test_unknown_principal_returns_empty_list():
    assert query_cloudtrail("no-such-principal") == []


def test_metadata_key_returns_empty_list():
    assert query_cloudtrail("_comment") == []


def test_known_principal_with_no_activity_returns_empty_list(monkeypatch, tmp_path):
    (tmp_path / "cloudtrail_events.json").write_text(json.dumps({"idle-principal": []}))
    monkeypatch.setenv("STEWARD_FIXTURES_DIR", str(tmp_path))

    assert query_cloudtrail("idle-principal") == []


def test_capped_at_50_events(monkeypatch, tmp_path):
    events = [
        {
            "eventTime": f"2026-07-13T07:{m:02d}:00+00:00",
            "eventName": "DescribeInstances",
            "eventSource": "ec2.amazonaws.com",
            "sourceIPAddress": "198.51.100.77",
            "awsRegion": "eu-west-2",
            "errorCode": None,
        }
        for m in range(60)
    ]
    (tmp_path / "cloudtrail_events.json").write_text(json.dumps({"busy": events}))
    monkeypatch.setenv("STEWARD_FIXTURES_DIR", str(tmp_path))

    result = query_cloudtrail("busy", hours=24)

    assert len(result) == MAX_EVENTS == 50


def test_nonpositive_hours_rejected():
    with pytest.raises(ValueError):
        query_cloudtrail("svc-scanner", hours=0)


def test_deterministic():
    assert query_cloudtrail("svc-scanner", hours=48) == query_cloudtrail("svc-scanner", hours=48)


def test_live_mode_is_not_silently_fixture_backed(monkeypatch):
    monkeypatch.setenv("STEWARD_LIVE", "1")
    with pytest.raises(NotImplementedError):
        query_cloudtrail("svc-scanner")
