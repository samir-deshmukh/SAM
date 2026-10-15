import csv
from pathlib import Path

from backend.admin.processing import _stage_csv


class FakeConnection:
    def __init__(self):
        self.rows = []

    def execute(self, query, values):
        if "INSERT INTO import_staging_records" in query:
            self.rows.append(values)
        else:
            raise AssertionError(f"Unexpected SQL in test: {query}")


def test_file_validation_failure_does_not_mark_every_cutoff_row_as_row_error(tmp_path):
    csv_path = tmp_path / "BCA_26_C2_cutoffs.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["institution_code", "institution_name", "program_name", "category", "percentage", "page"],
        )
        writer.writeheader()
        writer.writerow({"institution_code": "01001", "institution_name": "College A", "program_name": "BCA", "category": "GOPENH", "percentage": "90.1", "page": "1"})
        writer.writerow({"institution_code": "01002", "institution_name": "College B", "program_name": "BCA", "category": "ZZZ", "percentage": "80.2", "page": "2"})

    conn = FakeConnection()
    rows, quarantined = _stage_csv(
        conn, 56, "CUTOFFS", csv_path, False,
        "=== UNKNOWN CATEGORIES (1) ===\n[ZZZ] : 1\nTotal issues: 1",
        ("institution_code", "program_name", "category", "percentage"),
    )

    assert rows == 2
    assert quarantined == 1
    assert [row[6] for row in conn.rows] == ["FILE_REVIEW", "REVIEW"]
    assert "Unknown category" in conn.rows[1][7]
    assert "Total issues" not in conn.rows[0][7]
