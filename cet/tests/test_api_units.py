from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import backend.api as api


def request_for(ip="127.0.0.1"):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": [],
            "client": (ip, 12345),
            "scheme": "http",
        }
    )


def test_rate_limit_blocks_after_configured_threshold(monkeypatch):
    api._request_history.clear()
    monkeypatch.setattr(api, "RATE_LIMIT_MAX_REQUESTS", 2)
    request = request_for("10.0.0.1")

    api.check_rate_limit(request)
    api.check_rate_limit(request)
    with pytest.raises(HTTPException) as exc:
        api.check_rate_limit(request)

    assert exc.value.status_code == 429
    api._request_history.clear()


def test_db_available_reports_connection_failure():
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("connection failed")

    assert not api._db_available(BrokenEngine())


def test_public_options_uses_database_values(monkeypatch):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query):
            return [("Amravati",), ("Pune",)]

    class Engine:
        def connect(self):
            return Connection()

    monkeypatch.setattr(api, "get_active_engine", lambda: Engine())
    monkeypatch.setattr(api, "_db_available", lambda engine: True)
    monkeypatch.setattr(api, "available_program_families", lambda engine: ["BCA", "MCA"])
    api._request_history.clear()

    result = api.public_options(request_for("10.0.0.2"))

    assert result == {"cities": ["Amravati", "Pune"], "courses": ["BCA", "MCA"]}


def test_search_colleges_builds_bounded_cards(monkeypatch):
    class Engine:
        pass

    raw = pd.DataFrame(
        [
            {
                "institution_code": "01102",
                "institution_name": "Example College",
                "city": "Amravati",
                "website": "https://example.edu",
                "cutoff_percentile": 80.0,
                "year": 2026,
            },
            {
                "institution_code": "01102",
                "institution_name": "Example College",
                "city": "Amravati",
                "website": "https://example.edu",
                "cutoff_percentile": 75.0,
                "year": 2025,
            },
        ]
    )
    monkeypatch.setattr(api, "get_active_engine", lambda: Engine())
    monkeypatch.setattr(api, "_db_available", lambda engine: True)
    monkeypatch.setattr(api, "available_program_families", lambda engine: ["BCA"])
    monkeypatch.setattr(api, "search_cutoffs_for_course", lambda *args, **kwargs: raw)
    monkeypatch.setattr(api, "_drawer_metadata", lambda *args: {})
    api._request_history.clear()

    result = api.search_colleges(
        request_for("10.0.0.3"),
        course="BCA",
        percentile=82.0,
        city=None,
        sort="comp",
        page=1,
        page_size=25,
    )

    assert result.total == 1
    assert result.results[0].institution_code == "01102"
    assert result.results[0].highest_cutoff == 80.0
    assert result.results[0].status == "safe"


def test_search_rejects_unknown_course(monkeypatch):
    class Engine:
        pass

    monkeypatch.setattr(api, "get_active_engine", lambda: Engine())
    monkeypatch.setattr(api, "_db_available", lambda engine: True)
    monkeypatch.setattr(api, "available_program_families", lambda engine: ["BCA"])
    api._request_history.clear()

    with pytest.raises(HTTPException) as exc:
        api.search_colleges(
            request_for("10.0.0.4"),
            course="NOT_REAL",
            percentile=80.0,
            city=None,
            sort="comp",
            page=1,
            page_size=25,
        )

    assert exc.value.status_code == 400


def test_drawer_metadata_is_compact_and_bounded():
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, params):
            assert params["course"] == "BCA"
            assert "code_0" in params and "code_1" in params
            class Result:
                def fetchall(self):
                    return [
                        ("01102", False, 2026, "OPEN", "HU"),
                        ("01102", False, 2025, "OPEN", "OHU"),
                        ("01102", True, 2026, "SC", "SL"),
                    ]

            return Result()

    class Engine:
        def connect(self):
            return Connection()

    result = api._drawer_metadata(Engine(), "BCA", ["01102", "01103"])

    assert result == {
        "01102": {
            "y": [2025, 2026],
            "c": {
                "0": [{"v": "OPEN", "q": ["HU", "OHU"]}],
                "1": [{"v": "SC", "q": ["SL"]}],
            },
        }
    }
