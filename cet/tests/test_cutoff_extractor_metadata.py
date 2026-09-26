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


def test_extractor_uses_trusted_pdfium_backend():
    from scripts import cutoff_extractor

    assert cutoff_extractor.fitz.__name__.endswith("fitz_pdfium")


def test_program_code_with_letter_suffix_is_parsed():
    lines = merge_split_rank_lines([
        '01313 - Example College',
        '0131310170U - BCA',
    ])
    meta = extract_metadata(lines)
    assert meta['program_code'] == '0131310170U'
    assert meta['program_name'] == 'BCA'


def test_bare_roman_stage_prefix_is_normalized_before_rank():
    lines = merge_split_rank_lines([
        'GOPENH LOPENH',
        'I 2414',
        '(55.0372530)',
        '1047',
        '(75.3093618)',
    ])
    assert lines[0] == 'GOPENH LOPENH'
    assert lines[1] == 'Stage-I 2414 (55.0372530)'
    assert lines[2] == '1047 (75.3093618)'
