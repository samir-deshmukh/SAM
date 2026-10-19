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


def test_infer_city_from_name_uses_whole_phrase_and_longest_match():
    from backend.admin.resolver import infer_city_from_name
    cities = ["Pune", "Navi Mumbai", "Mumbai", "Nashik"]
    assert infer_city_from_name("Navi Mumbai Institute of Technology", cities) == "Navi Mumbai"
    assert infer_city_from_name("College of Engineering, Pune", cities) == "Pune"
    assert infer_city_from_name("Institute of Technology", cities) is None


def test_infer_city_from_name_does_not_match_short_substrings():
    from backend.admin.resolver import infer_city_from_name
    assert infer_city_from_name("Mumbaiwala Institute", ["Mumbai"]) is None
    assert infer_city_from_name("Vidarbha College", ["Nagpur", "Vidarbha"]) is None


def test_import_name_recovery_uses_real_staged_names_not_codes():
    import json
    from backend.admin.resolver import _import_names_for_codes

    class FakeResult:
        def fetchall(self):
            return [
                {"normalized_json": json.dumps({"institution_code": "1234", "institution_name": "Example Institute of Technology"})},
                {"normalized_json": json.dumps({"institution_code": "5678", "institution_name": "5678"})},
            ]

    class FakeConnection:
        def execute(self, query, params):
            assert "import_staging_records" in query
            assert params == ("1234", "5678")
            return FakeResult()

    assert _import_names_for_codes(FakeConnection(), ["1234", "5678"]) == {
        "1234": "Example Institute of Technology"
    }


def test_import_name_recovery_skips_query_when_no_codes():
    from backend.admin.resolver import _import_names_for_codes

    class FakeConnection:
        def execute(self, *args):
            raise AssertionError("Should not query without missing names")

    assert _import_names_for_codes(FakeConnection(), []) == {}
