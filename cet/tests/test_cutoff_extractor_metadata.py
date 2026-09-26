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
