import csv
from pathlib import Path

from backend.admin.processing import _resolve_cutoff_dimensions, _stage_csv


class FakeConnection:
    def __init__(self):
        self.rows = []

    def execute_many_values(self, query, values):
        assert "INSERT INTO import_staging_records" in query
        self.rows.extend(tuple(values[index:index + 8]) for index in range(0, len(values), 8))

    def execute(self, query, values):
        if "INSERT INTO import_staging_records" in query:
            self.rows.append(values)
            return None
        if "SELECT status FROM import_jobs" in query:
            class Result:
                @staticmethod
                def fetchone():
                    return {"status": "STAGING"}
            return Result()
        if "UPDATE import_jobs SET status" in query:
            return None
        raise AssertionError(f"Unexpected SQL in test: {query}")


def test_unknown_but_well_formed_category_is_accepted_and_file_issue_stays_file_level(tmp_path):
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
        "=== NEW CATEGORY CODES (accepted) (1) ===\n[ZZZ] : 1\nTotal issues: 0",
        ("institution_code", "program_name", "category", "percentage"),
    )

    assert rows == 2
    assert quarantined == 0
    assert [row[6] for row in conn.rows] == ["FILE_REVIEW", "FILE_REVIEW"]
    assert all("Unknown category" not in row[7] for row in conn.rows)
    assert "Total issues" not in conn.rows[0][7]


def test_new_cutoff_category_resolves_without_reference_whitelist_entry():
    assert _resolve_cutoff_dimensions({
        "category": "GNEWCODEH", "section": "", "stage": "Stage-I",
    }) == ("NEWCODE", False, "HU", "Stage-I")
