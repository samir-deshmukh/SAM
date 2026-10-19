from pathlib import Path

from backend import main as app_main


class _Result:
    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self, source_path: str, staged_count: int, result_count: int):
        self.source_path = source_path
        self.staged_count = staged_count
        self.result_count = result_count
        self.statements = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        self.statements.append((query, params))
        if "SELECT id,stored_path FROM import_jobs" in query:
            return _Result(rows=[{"id": 9, "stored_path": self.source_path}])
        if "SELECT COUNT(*) AS n FROM import_staging_records" in query:
            return _Result(row={"n": self.staged_count})
        if "SELECT COUNT(*) AS n FROM import_results" in query:
            return _Result(row={"n": self.result_count})
        return _Result()

    def commit(self):
        self.committed = True


def test_recovery_preserves_existing_staged_rows_and_requires_review(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"kept source")
    connection = _Connection("source.pdf", staged_count=12, result_count=1)
    monkeypatch.setattr(app_main, "BASE", tmp_path)
    monkeypatch.setattr(app_main, "connect", lambda: connection)
    events = []
    monkeypatch.setattr(app_main, "event", lambda *args, **kwargs: events.append((args, kwargs)))

    app_main._recover_interrupted_imports()

    sql = "\n".join(statement for statement, _ in connection.statements)
    assert "DELETE FROM import_staging_records" not in sql
    assert "DELETE FROM import_results" not in sql
    assert any("status='REVIEW_REQUIRED'" in statement for statement, _ in connection.statements)
    assert any("RECOVERY_REVIEW" in str(args) for args, _ in events)
    assert connection.committed


def test_recovery_requeues_only_when_no_staging_or_results_exist(monkeypatch, tmp_path: Path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"kept source")
    connection = _Connection("source.pdf", staged_count=0, result_count=0)
    monkeypatch.setattr(app_main, "BASE", tmp_path)
    monkeypatch.setattr(app_main, "connect", lambda: connection)
    monkeypatch.setattr(app_main, "event", lambda *args, **kwargs: None)

    app_main._recover_interrupted_imports()

    assert any("status='QUEUED'" in statement for statement, _ in connection.statements)
    assert not any("DELETE FROM import_staging_records" in statement for statement, _ in connection.statements)
    assert not any("DELETE FROM import_results" in statement for statement, _ in connection.statements)
