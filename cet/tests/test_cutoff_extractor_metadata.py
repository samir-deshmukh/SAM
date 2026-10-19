from scripts.cutoff_extractor import extract_metadata, merge_split_rank_lines


def test_split_status_and_home_university_metadata_are_recovered():
    lines = merge_split_rank_lines([
        '01102 - Example College, Amravati',
        '0110210110 - BCA',
        'Status:',
        'Un-Aided Linguistic Minority - Hindi Home University : Sant Gadge Baba Amravati University',
        'Home University Seats Allotted to Home University Candidates',
    ])
    meta = extract_metadata(lines)
    assert meta['institution_code'] == '01102'
    assert meta['status'] == 'Un-Aided Linguistic Minority - Hindi'
    assert meta['home_university'] == 'Sant Gadge Baba Amravati University'


def test_inline_status_and_home_university_are_split():
    lines = [
        '01102 - Example College, Amravati',
        '0110210110 - BCA',
        'Status: Un-Aided Linguistic Minority - Hindi Home University : Sant Gadge Baba Amravati University',
    ]
    meta = extract_metadata(lines)
    assert meta['institution_code'] == '01102'
    assert meta['status'] == 'Un-Aided Linguistic Minority - Hindi'
    assert meta['home_university'] == 'Sant Gadge Baba Amravati University'


def test_extractor_uses_hybrid_pdf_backends():
    from scripts import cutoff_extractor

    assert cutoff_extractor.fitz.__name__ == "fitz"
    assert cutoff_extractor._load_pdfium().__name__.endswith("fitz_pdfium")


def test_program_code_with_letter_suffix_is_parsed():
    lines = merge_split_rank_lines([
        '01313 - Example College',
        '0131310170U - BCA',
    ])
    meta = extract_metadata(lines)
    assert meta['program_code'] == '0131310170U'
    assert meta['program_name'] == 'BCA'


def test_bare_roman_rank_layout_is_not_promoted_to_stage():
    lines = merge_split_rank_lines([
        'GOPENH LOPENH',
        'I 2414',
        '(55.0372530)',
        '1047',
        '(75.3093618)',
    ])
    assert lines[0] == 'GOPENH LOPENH'
    assert lines[1] == 'I 2414 (55.0372530)'
    assert lines[2] == '1047 (75.3093618)'


def test_extractor_processes_selected_source_page_range_without_renumbering(tmp_path):
    import csv
    import json
    import fitz
    from scripts.cutoff_extractor import process_single_pdf

    pdf_path = tmp_path / "range.pdf"
    with fitz.open() as document:
        for index in range(3):
            page = document.new_page()
            page.insert_text((40, 40), "01002 - Example College, Amravati\n"
                "0100219110 - Civil Engineering\n"
                "Status: Government Autonomous Home University : Autonomous Institute\n"
                "State Level\nI\nGOPENH\n100 (90.0)", fontsize=8)
        document.save(pdf_path)

    output = tmp_path / "range-output"
    summary = process_single_pdf(
        pdf_path, output, dpi=300, lang="eng", use_camelot=False,
        use_pdfium=False, start_page=2, end_page=3, source_name="original.pdf",
    )
    assert summary["pages"] == 2
    with (output / "range_cutoffs.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    assert {int(row["page"]) for row in rows} == {2, 3}
    assert all(row["source_pdf"] == "original.pdf" for row in rows)
    audits = json.loads((output / "range_page_audit.json").read_text())
    assert [item["page"] for item in audits] == [2, 3]
