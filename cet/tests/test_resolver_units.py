from backend.admin.resolver import valid_url, verify_url


def test_valid_url_normalizes_safe_http_urls():
    assert valid_url("example.edu") == "https://example.edu/"
    assert valid_url("HTTP://example.edu/path") == "http://example.edu/path"


def test_valid_url_rejects_local_and_invalid_targets():
    assert valid_url("ftp://example.edu") is None
    assert valid_url("http://127.0.0.1:8000") is None
    assert valid_url("http://localhost") is None
    assert valid_url("") is None


def test_verify_url_rejects_invalid_url_without_network():
    result = verify_url("localhost", "Example College")
    assert result["ok"] is False
    assert result["note"] == "Invalid URL"
