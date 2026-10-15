import pytest

from backend import local_worker


@pytest.mark.parametrize(
    "backend_url",
    [
        "https://cetfind.onrender.com",
        "https://cetfind-backend.onrender.com",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
)
def test_backend_url_allows_only_expected_hosts(backend_url):
    assert local_worker._backend_ok(backend_url) == backend_url


@pytest.mark.parametrize(
    "backend_url",
    [
        "https://example.com",
        "http://192.168.1.5:8000",
        "file:///etc/passwd",
        "https://cetfind-backend.onrender.com.attacker.example",
    ],
)
def test_backend_url_rejects_untrusted_hosts(backend_url):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        local_worker._backend_ok(backend_url)


def test_production_admin_origins_are_allowlisted():
    assert "https://cetfind.onrender.com" in local_worker.ALLOWED_ORIGINS
    assert "https://cetfind-backend.onrender.com" in local_worker.ALLOWED_ORIGINS


def test_worker_binds_only_to_loopback_by_default():
    assert local_worker.ALLOWED_HOSTS <= {
        "cetfind.onrender.com",
        "cetfind-backend.onrender.com",
        "localhost",
        "127.0.0.1",
    }
