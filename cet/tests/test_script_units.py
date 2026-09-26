from pathlib import Path

import pandas as pd
import pytest

from scripts.cutoff_extractor import (
    clean_text,
    detect_section,
    extract_category_tokens,
    get_priority,
    is_category_token,
    split_by_stage,
)
from scripts.export_seats_json import alloc_sort_key, category_sort_key
from scripts.export_seats_json import category_sort_key as seat_category_sort_key
from scripts.validate_data import (
    forward_fill_block_columns,
    is_extraction_anomaly,
    parse_category,
    parse_filename as parse_cutoff_filename,
)
from scripts.validate_seats import parse_filename as parse_seat_filename


def test_cutoff_token_helpers():
    assert is_category_token("GOPENH")
    assert not is_category_token("STAGE")
    assert not is_category_token("12")
    assert extract_category_tokens("GOPENH LOPENH") == ["GOPENH", "LOPENH"]
    assert extract_category_tokens("GOPENH 12") == []


def test_cutoff_text_and_section_helpers():
    assert clean_text(" A\r\n\r\n\r\nB ") == "A\n\nB"
    assert detect_section("Home University Seats Allotted to Home University Candidates")
    assert detect_section("not a section") is None


def test_cutoff_stage_split_and_priority():
    assert split_by_stage("Stage-I 88.5 Stage-II 90.0") == [
        ("Stage-I", "88.5"),
        ("Stage-II", "90.0"),
    ]
    assert get_priority("native") > get_priority("ocr")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("GOPENH", ("OPEN", False, "HU")),
        ("LSCS", ("SC", True, "SL")),
        ("PWDROBCH", ("PWDROBC", False, "HU")),
        ("MI", ("MI", False, "SL")),
        ("", (None, None, None)),
    ],
)
def test_parse_category_rules(raw, expected):
    assert parse_category(raw) == expected


def test_forward_fill_only_uses_prior_nonblank_values():
    df = pd.DataFrame(
        {
            "institution_code": ["01102", "", "01103"],
            "institution_name": ["College A", "", "College B"],
            "program_code": ["101", "", "202"],
            "program_name": ["BCA", "", "MBA"],
            "status": ["Status A", "", "Status B"],
            "section": ["HU", "", "SL"],
            "home_university": ["University A", "", "University B"],
        }
    )

    count, first_blank = forward_fill_block_columns(df)

    assert count == 6
    assert first_blank == []
    assert df.loc[1, "institution_code"] == "01102"
    assert df.loc[1, "program_name"] == "BCA"


def test_extraction_anomaly_detection():
    assert is_extraction_anomaly(
        {"institution_code": "", "institution_name": "", "category": "OPEN"}
    )
    assert is_extraction_anomaly(
        {"institution_code": "01102", "institution_name": "College", "category": "GOVERNMENT"}
    )
    assert not is_extraction_anomaly(
        {"institution_code": "01102", "institution_name": "College", "category": "OPEN"}
    )


def test_validation_filename_parsers():
    assert parse_cutoff_filename(Path("BCA_26_C1.csv")) == {
        "family": "BCA",
        "year": 2026,
        "round": 1,
    }
    assert parse_cutoff_filename(Path("unknown.csv")) is None
    assert parse_seat_filename(Path("BCA_SM.csv")) == {"family": "BCA"}
    assert parse_seat_filename(Path("random.csv")) is None


def test_seat_sort_keys_are_stable():
    assert category_sort_key("OPEN") < category_sort_key("SC")
    assert alloc_sort_key("State Level") < alloc_sort_key("HU")
    assert seat_category_sort_key("OPEN") == category_sort_key("OPEN")
