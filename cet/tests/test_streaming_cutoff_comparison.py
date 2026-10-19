import csv
from pathlib import Path

from backend.admin.processing import _compare_cutoffs


class _Connection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query, _params):
        return iter(self.rows)


def _row(institution: str, rank: str, percentage: str, page: str) -> dict[str, str]:
    return {
        "source_pdf": "source.pdf", "page": page, "institution_code": institution,
        "institution_name": "Sample College", "program_code": "BCA", "program_name": "BCA",
        "status": "Government", "home_university": "University",
        "section": "Home University Seats Allotted to Home University Candidates",
        "stage": "Stage-I", "category": "GOPENH", "rank": rank,
        "rank_number": rank, "rank_suffix": "", "percentage": percentage,
        "percentage_raw": percentage, "raw_value": f"{rank}-{percentage}",
        "source": "native", "merged_from": "",
    }


def test_streaming_cutoff_comparison_counts_exact_changed_new_and_input_duplicates(tmp_path: Path):
    path = tmp_path / "BCA_26_C1.csv"
    rows = [
        _row("01001", "100", "90.0", "1"),  # Exact match in database
        _row("01001", "99", "89.0", "2"),   # Same identity, changed rank/percentile
        _row("01002", "200", "80.0", "3"),  # New candidate
        _row("01002", "200", "80.0", "4"),  # Duplicate in staged input
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    existing = [
        ("01001", "BCA", "OPEN", 0, "HU", "Stage-I", 100, None, 90.0),
    ]
    result = _compare_cutoffs(_Connection(existing), path, "BCA", 2026, "C1")

    assert result["rows_compared"] == 4
    assert result["already_present_exact_key"] == 1
    assert result["changed_candidates"] == 1
    assert result["new_candidates"] == 2
    assert result["duplicate_in_staged_input"] == 1
