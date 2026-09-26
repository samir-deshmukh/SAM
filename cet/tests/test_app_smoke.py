from __future__ import annotations

import importlib


def test_fastapi_application_imports():
    mod = importlib.import_module("backend.main")
    assert mod.app is not None


def test_public_api_imports_without_database_connection():
    mod = importlib.import_module("backend.api")
    assert getattr(mod, 'router', None) is not None


def test_streamlit_app_declares_postgres_only_connection_path():
    source = open("app/Home.py", encoding="utf-8").read()
    assert "DATABASE_URL" in source
    assert "sqlite" not in source.lower()
