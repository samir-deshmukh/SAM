import json

from backend.admin.db import Result
from backend.admin.publishing import verify_public_tree
from scripts.enrich_institutes import norm, validate_website
from scripts.pg_runtime import qmark_sql
from src.cet_cap import queries


class FakeResult:
    rowcount = 2

    def fetchone(self):
        return type("Row", (), {"_mapping": {"id": 1, "name": "A"}})()

    def fetchall(self):
        return [
            type("Row", (), {"_mapping": {"id": 1}})(),
            type("Row", (), {"_mapping": {"id": 2}})(),
        ]

    def __iter__(self):
        return iter(self.fetchall())


def test_result_wrapper_exposes_mapping_rows():
    result = Result(FakeResult(), inserted_id=17)
    assert result.rowcount == 2
    assert result.lastrowid == 17
    assert result.fetchone() == {"id": 1, "name": "A"}
    assert result.fetchall() == [{"id": 1}, {"id": 2}]
    assert list(result) == [{"id": 1}, {"id": 2}]


def test_pg_runtime_qmark_conversion():
    assert qmark_sql("SELECT ? FROM x WHERE id=?", ("name", 7)) == (
        "SELECT :p0 FROM x WHERE id=:p1",
        {"p0": "name", "p1": 7},
    )


def test_institute_helpers_validate_and_normalize():
    assert validate_website("https://example.edu") == "https://example.edu/"
    assert validate_website("not a url") is None
    assert norm("Sant Gadge-Baba University") == "SANT GADGE BABA UNIVERSITY"


def test_query_helpers_read_rows_from_engine():
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query):
            return [(2026,), (2025,)]

    class Engine:
        def connect(self):
            return Connection()

    engine = Engine()
    assert queries.available_years(engine) == [2026, 2025]
    assert queries.available_program_families(engine) == [2026, 2025]
    assert queries.available_categories(engine) == [2026, 2025]


def test_public_tree_verification_accepts_valid_runtime(tmp_path):
    public = tmp_path / "site"
    data = public / "data"
    data.mkdir(parents=True)
    (data / "search_index.js").write_text("window.SEARCH = [];", encoding="utf-8")
    (data / "runtime-manifest.json").write_text(json.dumps({"version": 1}), encoding="utf-8")
    (data / "small.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    result = verify_public_tree(public)

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["file_count"] == 3


def test_public_tree_verification_rejects_private_key(tmp_path):
    public = tmp_path / "site"
    data = public / "data"
    data.mkdir(parents=True)
    (data / "search_index.js").write_text("window.SEARCH = [];", encoding="utf-8")
    (data / "runtime-manifest.json").write_text("{}", encoding="utf-8")
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    (data / "bad.json").write_text(json.dumps(marker), encoding="utf-8")

    result = verify_public_tree(public)

    assert result["ok"] is False
    assert any("secret pattern" in error for error in result["errors"])
