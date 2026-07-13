"""Phase 0: the entrypoint honours the canned-response contract, offline."""

from main import invoke


def test_invoke_returns_canned_response_echoing_payload():
    payload = {"finding_id": "ssh-bruteforce"}

    result = invoke(payload, None)

    assert result["agent"] == "stewards-enquiry"
    assert result["status"] == "ok"
    assert result["received"] == payload
