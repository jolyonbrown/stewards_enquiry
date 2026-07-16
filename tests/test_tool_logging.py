"""Invariant 5: every tool call emits one structured JSON log line."""

import json
import logging

import pytest

from tools import get_finding, lookup_ip


def parsed_tool_lines(caplog):
    return [json.loads(r.message) for r in caplog.records if r.name == "stewards_enquiry.tools"]


def test_successful_call_logs_one_structured_line(caplog):
    with caplog.at_level(logging.INFO, logger="stewards_enquiry.tools"):
        lookup_ip("203.0.113.42")

    lines = parsed_tool_lines(caplog)
    assert len(lines) == 1
    line = lines[0]
    assert line["event"] == "tool_call"
    assert line["tool"] == "lookup_ip"
    assert line["outcome"] == "ok"
    assert line["duration_ms"] >= 0
    assert len(line["input_digest"]) == 12


def test_failing_call_still_logs_with_error_outcome(caplog):
    with (
        caplog.at_level(logging.INFO, logger="stewards_enquiry.tools"),
        pytest.raises(ValueError),
    ):
        get_finding("does-not-exist")

    lines = parsed_tool_lines(caplog)
    assert len(lines) == 1
    assert lines[0]["tool"] == "get_finding"
    assert lines[0]["outcome"] == "error:ValueError"


def test_same_input_same_digest_different_input_different_digest(caplog):
    with caplog.at_level(logging.INFO, logger="stewards_enquiry.tools"):
        lookup_ip("203.0.113.42")
        lookup_ip("203.0.113.42")
        lookup_ip("198.51.100.77")

    digests = [line["input_digest"] for line in parsed_tool_lines(caplog)]
    assert digests[0] == digests[1]
    assert digests[0] != digests[2]


def test_raw_input_never_appears_in_the_log_line(caplog):
    with caplog.at_level(logging.INFO, logger="stewards_enquiry.tools"):
        lookup_ip("203.0.113.42")

    assert "203.0.113.42" not in caplog.records[-1].message


def test_tool_lines_are_visible_under_default_config_after_configure_logging(caplog):
    """PR #1 review finding: INFO lines were dropped at the root WARNING
    threshold in real runs, and at_level in tests concealed it. After
    configure_logging() (called by main.py), lines must flow with NO
    explicit level manipulation here."""
    from telemetry import configure_logging

    configure_logging()
    lookup_ip("203.0.113.42")

    assert any(r.name == "stewards_enquiry.tools" for r in caplog.records)
