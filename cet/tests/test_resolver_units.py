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


def test_valid_url_rejects_private_ip_and_credentials():
    assert valid_url("http://192.168.1.10/admin") is None
    assert valid_url("http://169.254.169.254/latest/meta-data") is None
    assert valid_url("http://user:pass@example.edu") is None


def test_verify_url_rejects_private_dns_result(monkeypatch):
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.4", 443))],
    )
    result = verify_url("https://example.edu", "Example College")
    assert result["ok"] is False
    assert "non-public" in result["note"]
