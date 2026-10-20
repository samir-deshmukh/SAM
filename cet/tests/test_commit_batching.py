from backend.admin.processing import _iter_staged_rows


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _PagedConnection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        job_id, result_type, last_id, batch_size = params
        assert job_id == 91
        assert result_type == "SEATS"
        return _Result([
            row for row in self.rows
            if row["id"] > last_id and row["job_id"] == job_id and row["result_type"] == result_type
        ][:batch_size])


def test_iter_staged_rows_uses_bounded_keyset_pages():
    rows = [
        {"id": index, "job_id": 91, "result_type": "SEATS", "normalized_json": str(index)}
        for index in range(1, 8)
    ]
    connection = _PagedConnection(rows)

    result = list(_iter_staged_rows(connection, 91, "SEATS", batch_size=3))

    assert [row["id"] for row in result] == list(range(1, 8))
    assert [call[1][2:] for call in connection.calls] == [(0, 3), (3, 3), (6, 3), (7, 3)]
    assert all("id>?" in query and "LIMIT ?" in query for query, _ in connection.calls)
