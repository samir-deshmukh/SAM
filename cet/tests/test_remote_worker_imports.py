from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.requests import Request

from backend import main


def _request():
    return Request({
        'type': 'http', 'http_version': '1.1', 'method': 'POST',
        'scheme': 'https', 'path': '/admin/api/remote-worker/imports',
        'raw_path': b'/admin/api/remote-worker/imports', 'query_string': b'',
        'headers': [], 'client': ('testclient', 123), 'server': ('testserver', 443),
    })


def test_remote_upload_fails_closed_without_private_durable_storage(monkeypatch):
    monkeypatch.setenv('CAPFIND_REMOTE_WORKER_TOKEN', 'x' * 40)
    monkeypatch.setattr(main, 'require', lambda *args, **kwargs: {'uid': 1})
    monkeypatch.setattr(main, 'storage_backend', lambda: 'local')
    upload = UploadFile(filename='generic.pdf', file=BytesIO(b'%PDF-valid'))

    with pytest.raises(HTTPException) as error:
        main.create_remote_worker_import(_request(), upload)

    assert error.value.status_code == 503
    assert 'private durable' in error.value.detail


@pytest.mark.parametrize(
    ('configured', 'authorization', 'expected_status'),
    [('', 'Bearer arbitrary', 503), ('x' * 40, 'Bearer wrong', 401)],
)
def test_remote_worker_claim_requires_shared_secret(monkeypatch, configured, authorization, expected_status):
    monkeypatch.setenv('CAPFIND_REMOTE_WORKER_TOKEN', configured)
    request = _request()
    request.scope['headers'] = [(b'authorization', authorization.encode())]

    with pytest.raises(HTTPException) as error:
        main._remote_worker_auth(request)

    assert error.value.status_code == expected_status
