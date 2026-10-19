import csv
import json
from pathlib import Path

import fitz

from scripts.chunked_cutoff_extractor import (
    iter_json_array, remap_chunk_artifacts, split_pdf, validate_chunk_artifacts,
)


def test_split_pdf_preserves_requested_page_range(tmp_path: Path):
    source = fitz.open()
    for index in range(7):
        page = source.new_page()
        page.insert_text((72, 72), f"source-page-{index + 1}")
    part_path = tmp_path / "part.pdf"

    split_pdf(source, part_path, 2, 5)
    source.close()

    with fitz.open(part_path) as part:
        assert len(part) == 3
        text = [page.get_text() for page in part]
    assert ["source-page-3" in text[0], "source-page-4" in text[1],
            "source-page-5" in text[2]] == [True, True, True]


def test_remap_chunk_artifacts_restores_original_page_numbers(tmp_path: Path):
    stem = "part_0002"
    chunk_dir = tmp_path / stem
    chunk_dir.mkdir()
    csv_path = chunk_dir / f"{stem}_cutoffs.csv"
    json_path = chunk_dir / f"{stem}_cutoffs.json"
    audit_path = chunk_dir / f"{stem}_page_audit.json"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_pdf", "page", "rank"])
        writer.writeheader()
        writer.writerow({"source_pdf": f"{stem}.pdf", "page": 1, "rank": 123})
        writer.writerow({"source_pdf": f"{stem}.pdf", "page": 2, "rank": 456})
    json_path.write_text(json.dumps([
        {"source_pdf": f"{stem}.pdf", "page": 1, "rank": 123},
        {"source_pdf": f"{stem}.pdf", "page": 2, "rank": 456},
    ]), encoding="utf-8")
    audit_path.write_text(json.dumps([{"page": 1}, {"page": 2}]), encoding="utf-8")

    _, _, _, row_count = remap_chunk_artifacts(
        chunk_dir, stem, "original.pdf", page_offset=100
    )

    assert row_count == 2
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["page"] for row in rows] == ["101", "102"]
    assert all(row["source_pdf"] == "original.pdf" for row in rows)
    assert [row["page"] for row in json.loads(json_path.read_text())] == [101, 102]
    assert [row["page"] for row in json.loads(audit_path.read_text())] == [101, 102]


def test_streaming_json_array_reader_handles_multiline_arrays(tmp_path: Path):
    path = tmp_path / "rows.json"
    path.write_text('[\n  {"page": 1, "name": "a"},\n  {\n    "page": 2, "name": "b"\n  }\n]')
    assert list(iter_json_array(path)) == [
        {"page": 1, "name": "a"}, {"page": 2, "name": "b"}
    ]


def test_validate_chunk_artifacts_checks_row_provenance_and_page_coverage(tmp_path: Path):
    stem = "source"
    csv_path = tmp_path / f"{stem}_cutoffs.csv"
    json_path = tmp_path / f"{stem}_cutoffs.json"
    audit_path = tmp_path / f"{stem}_page_audit.json"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_pdf", "page", "rank"])
        writer.writeheader()
        writer.writerow({"source_pdf": "original.pdf", "page": 11, "rank": 123})
        writer.writerow({"source_pdf": "original.pdf", "page": 12, "rank": 456})
    json_path.write_text('[{"source_pdf":"original.pdf","page":11,"rank":"123"},\n{"source_pdf":"original.pdf","page":12,"rank":"456"}]')
    audit_path.write_text('[{"page":11},{"page":12}]')
    _, _, _, count = validate_chunk_artifacts(tmp_path, stem, "original.pdf", 11, 12)
    assert count == 2

    audit_path.write_text('[{"page":11}]')
    try:
        validate_chunk_artifacts(tmp_path, stem, "original.pdf", 11, 12)
    except RuntimeError as exc:
        assert "Page-audit coverage mismatch" in str(exc)
    else:
        raise AssertionError("Incomplete page audit must be rejected")

    audit_path.write_text('[{"page":11},{"page":12}]')
    json_path.write_text('[{"source_pdf":"original.pdf","page":11,"rank":"999"},\n{"source_pdf":"original.pdf","page":12,"rank":"456"}]')
    try:
        validate_chunk_artifacts(tmp_path, stem, "original.pdf", 11, 12)
    except RuntimeError as exc:
        assert "CSV/JSON data mismatch" in str(exc)
    else:
        raise AssertionError("CSV/JSON field mismatches must be rejected")


def test_chunked_extraction_matches_whole_file_outputs_without_data_loss(tmp_path: Path):
    import hashlib
    import subprocess
    import sys

    source = tmp_path / "synthetic_cap.pdf"
    with fitz.open() as document:
        for _ in range(3):
            page = document.new_page()
            page.insert_text(
                (40, 40),
                "01002 - Example College, Amravati\n"
                "0100219110 - Civil Engineering\n"
                "Status: Government Autonomous Home University : Autonomous Institute\n"
                "State Level\nI\nGOPENH\n100 (90.0)",
                fontsize=8,
            )
        document.save(source)

    script_dir = Path(__file__).resolve().parents[1] / "scripts"
    direct_out = tmp_path / "direct"
    chunked_out = tmp_path / "chunked"
    provenance = ["--source-name", "original-upload.pdf"]
    direct = subprocess.run(
        [sys.executable, str(script_dir / "cutoff_extractor.py"), str(source),
         "--out", str(direct_out), *provenance, "--native-only"],
        cwd=script_dir.parent, capture_output=True, text=True, timeout=30,
    )
    assert direct.returncode == 0, direct.stderr + direct.stdout

    chunked = subprocess.run(
        [sys.executable, str(script_dir / "chunked_cutoff_extractor.py"), str(source),
         "--out", str(chunked_out), "--chunk-pages", "250", *provenance],
        cwd=script_dir.parent, capture_output=True, text=True, timeout=30,
    )
    assert chunked.returncode == 0, chunked.stderr + chunked.stdout

    names = [
        "synthetic_cap_cutoffs.csv",
        "synthetic_cap_cutoffs.json",
        "synthetic_cap_page_audit.json",
    ]
    for name in names:
        direct_file = direct_out / name
        chunked_file = chunked_out / name
        assert direct_file.is_file() and chunked_file.is_file()
        assert hashlib.sha256(direct_file.read_bytes()).digest() == hashlib.sha256(chunked_file.read_bytes()).digest()

    manifest = json.loads((chunked_out / ".chunk_work" / "manifest.json").read_text())
    assert manifest["status"] == "COMPLETED"
    assert manifest["result"]["rows_extracted"] > 0
    assert manifest["result"]["page_audit_entries"] == 3
    with (chunked_out / names[0]).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert {int(row["page"]) for row in rows} == {1, 2, 3}
    assert all(row["source_pdf"] == "original-upload.pdf" for row in rows)
