import csv
from pathlib import Path

from scripts.clean_data import REQUIRED_COLUMNS, clean_file


def _write_input(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_clean_file_streams_rows_and_quarantines_blank_categories(tmp_path: Path):
    source = tmp_path / "input.csv"
    rows = []
    for index in range(25000):
        row = {column: "" for column in REQUIRED_COLUMNS}
        row.update({"source_pdf": "source.pdf", "page": str(index // 10 + 1),
                    "institution_code": f"{index:05d}", "program_name": "BTech",
                    "category": "" if index in {3, 17000} else "GOPENH",
                    "percentage": "91.25"})
        rows.append(row)
    _write_input(source, rows)

    result = clean_file(source, tmp_path / "clean", tmp_path / "rejects")

    assert result == {
        "file": "input.csv", "rows_in": 25000, "rows_kept": 24998,
        "rows_quarantined": 2,
        "reject_path": str(tmp_path / "rejects" / "input_rejects.csv"),
    }
    with (tmp_path / "clean" / "input.csv").open(encoding="utf-8", newline="") as stream:
        cleaned = list(csv.DictReader(stream))
    with (tmp_path / "rejects" / "input_rejects.csv").open(encoding="utf-8", newline="") as stream:
        rejected = list(csv.DictReader(stream))
    assert len(cleaned) == 24998
    assert len(rejected) == 2
    assert all(row["category"] for row in cleaned)
    assert all(row["reject_reason"] == "blank_category_upstream_pdf_extraction" for row in rejected)


def test_clean_file_skips_wrong_schema_without_replacing_previous_output(tmp_path: Path):
    source = tmp_path / "seats.csv"
    source.write_text("institution_code,category\n123,GOPEN\n", encoding="utf-8")
    out_dir = tmp_path / "clean"
    out_dir.mkdir()
    previous = out_dir / "seats.csv"
    previous.write_text("previous-good-output\n", encoding="utf-8")

    assert clean_file(source, out_dir, tmp_path / "rejects") is None
    assert previous.read_text(encoding="utf-8") == "previous-good-output\n"
    assert not (out_dir / "seats.csv.tmp").exists()
