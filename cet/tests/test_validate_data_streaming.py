import csv
from pathlib import Path

from scripts.validate_data import REQUIRED_COLUMNS, validate_single_file_streaming


def test_streaming_validator_preserves_forward_fill_and_duplicate_semantics(tmp_path: Path):
    path = tmp_path / "BCA_26_C1.csv"
    base = {column: "" for column in REQUIRED_COLUMNS}
    base.update({
        "source_pdf": "source.pdf", "page": "1", "institution_code": "01001",
        "institution_name": "Sample College", "program_code": "BCA",
        "program_name": "BCA", "status": "Government", "home_university": "University",
        "section": "Home University Seats Allotted to Home University Candidates",
        "stage": "Stage-I", "category": "GOPENH", "rank": "1", "rank_number": "1",
        "rank_suffix": "", "percentage": "90.0", "percentage_raw": "90.0",
        "raw_value": "1-90.0", "source": "native", "merged_from": "",
    })
    duplicate = dict(base, source_pdf="source.pdf", page="2")
    for column in ("institution_code", "institution_name", "program_code", "program_name", "status", "section"):
        duplicate[column] = ""
    distinct = dict(base, page="3", rank="2", rank_number="2", percentage="89.0", percentage_raw="89.0")

    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows([base, duplicate, distinct])

    result = validate_single_file_streaming(
        path, {"OPEN"}, {"HU"}, {"Stage-I"}, {"BCA"}
    )

    assert result["summary"]["rows"] == 3
    assert result["summary"]["dups"] == 2
    assert result["forward_fill_count"] == 6
    assert result["summary"]["bad_cat"] == 0
    assert result["summary"]["bad_stage"] == 0
    assert result["summary"]["bad_section"] == 0
    assert result["summary"]["bad_prog"] == 0
    assert result["summary"]["bad_pct"] == 0
    assert not result["file_error"] if "file_error" in result else True
