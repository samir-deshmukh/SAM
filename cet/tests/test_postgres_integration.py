"""PostgreSQL end-to-end contract tests.

Run with TEST_DATABASE_URL pointing at an isolated PostgreSQL database.
These tests intentionally never create or use a file database.
"""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
import pytest
from sqlalchemy import text

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='TEST_DATABASE_URL is required')
ROOT=Path(__file__).resolve().parents[1]

def run(*args):
    return subprocess.run([sys.executable,*args],cwd=ROOT,capture_output=True,text=True,check=True)

def db():
    from src.cet_cap.db import get_engine
    return get_engine(os.environ['TEST_DATABASE_URL'])

def test_schema_seed_cutoff_ingest_is_idempotent(tmp_path):
    from scripts.db_bootstrap import bootstrap_schema
    e=db(); bootstrap_schema(e)
    run('scripts/seed_reference_tables.py','--db-url',os.environ['TEST_DATABASE_URL'],'--raw-dir','data/raw','--ref-dir','data/reference')
    first=run('scripts/ingest.py','data/raw','--db-url',os.environ['TEST_DATABASE_URL'],'--ref-dir','data/reference')
    assert 'failed=0' in first.stdout
    with e.connect() as c:
        n=c.execute(text('SELECT count(*) FROM cutoffs')).scalar_one()
        assert n > 0
    second=run('scripts/ingest.py','data/raw','--db-url',os.environ['TEST_DATABASE_URL'],'--ref-dir','data/reference')
    assert 'failed=0' in second.stdout and 'duplicate=' in second.stdout
    with e.connect() as c:
        assert c.execute(text('SELECT count(*) FROM cutoffs')).scalar_one()==n

def test_seat_ingest_and_runtime_are_authoritative(tmp_path):
    from scripts.db_bootstrap import bootstrap_schema
    e=db(); bootstrap_schema(e)
    run('scripts/seed_reference_tables.py','--db-url',os.environ['TEST_DATABASE_URL'])
    run('scripts/ingest_seats.py','data/raw/seats','--year','2026','--db-url',os.environ['TEST_DATABASE_URL'])
    out=tmp_path/'runtime'
    run('scripts/export_seats_json.py','--db-url',os.environ['TEST_DATABASE_URL'],'--out',str(out))
    assert list(out.glob('seats_*.json'))

def test_search_index_and_enrichment_are_db_backed(tmp_path):
    from scripts.db_bootstrap import bootstrap_schema
    e=db(); bootstrap_schema(e)
    run('scripts/seed_reference_tables.py','--db-url',os.environ['TEST_DATABASE_URL'])
    run('scripts/ingest.py','data/raw','--db-url',os.environ['TEST_DATABASE_URL'])
    run('scripts/enrich_institutes.py','data/reference/institute_contacts.csv','--db-url',os.environ['TEST_DATABASE_URL'])
    out=tmp_path/'runtime'; run('scripts/export_search_index.py','--db-url',os.environ['TEST_DATABASE_URL'],'--out',str(out))
    records=json.loads((out/'search_index.json').read_text())
    assert records and all('institution_code' in r for r in records)


def test_public_search_returns_matching_college_from_postgres(monkeypatch):
    """Exercise the public search handler and SQL against an isolated PostgreSQL fixture."""
    import uuid
    from starlette.requests import Request
    import backend.api as api
    from scripts.db_bootstrap import bootstrap_schema

    engine = db()
    bootstrap_schema(engine)
    suffix = uuid.uuid4().hex[:10].upper()
    family = f"E2E{suffix}"
    code = f"E{suffix}"
    name = f"Search Fixture College {suffix}"
    program_id = None
    api._request_history.clear()
    api._PUBLIC_CACHE.clear()
    api._SEARCH_METADATA_CACHE.clear()
    monkeypatch.setattr(api, "get_active_engine", lambda: engine)
    try:
        with engine.begin() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS college_website_resolver (
                institution_code TEXT PRIMARY KEY, status TEXT, website TEXT
            )"""))
            conn.execute(text("INSERT INTO institutes(institution_code,institution_name,city,district) VALUES (:code,:name,'Amravati','Pune')"), {"code": code, "name": name})
            program_id = conn.execute(text("INSERT INTO programs(program_family,program_name_raw) VALUES (:family,:name) RETURNING program_id"), {"family": family, "name": family}).scalar_one()
            conn.execute(text("INSERT INTO base_categories(base_code) VALUES (:category) ON CONFLICT DO NOTHING"), {"category": f"T{suffix}"})
            conn.execute(text("INSERT INTO sections(section_code,section_full) VALUES (:section,'Fixture') ON CONFLICT DO NOTHING"), {"section": f"S{suffix}"})
            conn.execute(text("INSERT INTO stages(stage_code) VALUES (:stage) ON CONFLICT DO NOTHING"), {"stage": f"ST{suffix}"})
            conn.execute(text("""INSERT INTO cutoffs(year,round,institution_code,program_id,base_category,is_ladies,section_code,stage_code,rank_number,percentile,raw_category,raw_program_name,source_pdf)
                VALUES (2025,1,:code,:program_id,:category,FALSE,:section,:stage,1234,75.5,:raw_category,:family,'fixture.pdf')"""), {
                "code": code, "program_id": program_id, "category": f"T{suffix}",
                "section": f"S{suffix}", "stage": f"ST{suffix}",
                "raw_category": f"G{suffix}", "family": family,
            })
            conn.execute(text("""INSERT INTO cutoff_college_year_summary(program_family,institution_code,year,low_percentile,high_percentile,low_rank)
                VALUES (:family,:code,2025,75.5,75.5,1234)"""), {"family": family, "code": code})
            conn.execute(text("""INSERT INTO college_search_runtime(program_family,institution_code,lowest_rank)
                VALUES (:family,:code,1234)"""), {"family": family, "code": code})
            conn.execute(text("""INSERT INTO college_search_cutoff_points(program_family,institution_code,percentile)
                VALUES (:family,:code,75.5)"""), {"family": family, "code": code})

        request = Request({"type": "http", "method": "GET", "path": "/api/search",
                           "query_string": b"", "headers": [],
                           "client": ("127.0.0.1", 12345), "scheme": "http"})
        result = api.search_colleges(request, course=family, percentile=80.0,
                                     city="Amravati", sort="comp", page=1, page_size=50)

        assert result.total == 1
        assert len(result.results) == 1
        card = result.results[0]
        assert card.institution_code == code
        assert card.name == name
        assert card.city == "Amravati"
        assert card.highest_cutoff == 75.5
        assert card.history == [{"year": 2025, "percentile": 75.5, "low": 75.5, "high": 75.5, "rank": 1234}]

        district_result = api.search_colleges(
            request, course=family, percentile=80.0, city="Pune",
            location_type="district", sort="comp", page=1, page_size=50,
        )
        assert district_result.total == 1
        assert district_result.results[0].institution_code == code

        city_result = api.search_colleges(
            request, course=family, percentile=80.0, city="Pune",
            location_type="city", sort="comp", page=1, page_size=50,
        )
        assert city_result.total == 0

        # Before the derived-data rebuild, the legacy raw-table query remains
        # available and returns the same result.
        from src.cet_cap.queries import search_college_summary_page
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM college_search_cutoff_points WHERE institution_code=:code"), {"code": code})
            conn.execute(text("DELETE FROM college_search_runtime WHERE institution_code=:code"), {"code": code})
        legacy, legacy_total = search_college_summary_page(
            engine, 80.0, family, "Amravati", "comp", 1, 50
        )
        assert legacy_total == 1
        assert legacy.iloc[0]["institution_code"] == code
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM cutoff_college_year_summary WHERE institution_code=:code"), {"code": code})
            conn.execute(text("DELETE FROM college_search_cutoff_points WHERE institution_code=:code"), {"code": code})
            conn.execute(text("DELETE FROM college_search_runtime WHERE institution_code=:code"), {"code": code})
            conn.execute(text("DELETE FROM cutoffs WHERE institution_code=:code"), {"code": code})
            if program_id is not None:
                conn.execute(text("DELETE FROM programs WHERE program_id=:program_id"), {"program_id": program_id})
            conn.execute(text("DELETE FROM institutes WHERE institution_code=:code"), {"code": code})
            conn.execute(text("DELETE FROM base_categories WHERE base_code=:category"), {"category": f"T{suffix}"})
            conn.execute(text("DELETE FROM sections WHERE section_code=:section"), {"section": f"S{suffix}"})
            conn.execute(text("DELETE FROM stages WHERE stage_code=:stage"), {"stage": f"ST{suffix}"})
        api.invalidate_public_caches()


def test_refresh_builds_exact_search_serving_index():
    """The transactional derived-data build preserves raw-search eligibility semantics."""
    import uuid
    from scripts.db_bootstrap import bootstrap_schema
    from scripts.refresh_derived_data import refresh
    from src.cet_cap.queries import search_college_summary_page

    engine = db()
    bootstrap_schema(engine)
    suffix = uuid.uuid4().hex[:10].upper()
    family = f"SEARCH{suffix}"
    institution = f"S{suffix}"
    category = f"C{suffix}"
    section = f"Q{suffix}"
    stage = f"T{suffix}"
    lane = f"L{suffix}"
    program_id = None

    try:
        with engine.begin() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS college_website_resolver (
                institution_code TEXT PRIMARY KEY, status TEXT, website TEXT
            )"""))
            conn.execute(
                text("INSERT INTO institutes(institution_code,institution_name,city) VALUES (:code,:name,'Pune')"),
                {"code": institution, "name": f"Search Runtime Fixture {suffix}"},
            )
            program_id = conn.execute(
                text("INSERT INTO programs(program_family,program_name_raw) VALUES (:family,:name) RETURNING program_id"),
                {"family": family, "name": f"Search Runtime Branch {suffix}"},
            ).scalar_one()
            conn.execute(text("INSERT INTO base_categories(base_code) VALUES (:code)"), {"code": category})
            conn.execute(text("INSERT INTO sections(section_code,section_full) VALUES (:code,'Fixture')"), {"code": section})
            conn.execute(text("INSERT INTO stages(stage_code) VALUES (:code)"), {"code": stage})
            conn.execute(text("INSERT INTO allocation_lanes(lane_code,lane_full) VALUES (:code,'Fixture')"), {"code": lane})

            cutoff_rows = [
                (2025, 1, 70.0, 500, False),
                (2026, 1, 80.0, 300, True),
                (2026, 2, 0.0, 0, False),  # known extraction artifact: excluded by search
            ]
            for year, round_no, percentile, rank, ladies in cutoff_rows:
                conn.execute(text("""INSERT INTO cutoffs(
                    year,round,institution_code,program_id,base_category,is_ladies,
                    section_code,stage_code,rank_number,percentile,raw_category,
                    raw_program_name,source_pdf
                ) VALUES (:year,:round,:institution,:program,:category,:ladies,
                         :section,:stage,:rank,:percentile,'OPEN','Fixture','fixture.pdf')"""), {
                    "year": year, "round": round_no, "institution": institution,
                    "program": program_id, "category": category, "ladies": ladies,
                    "section": section, "stage": stage, "rank": rank,
                    "percentile": percentile,
                })

            conn.execute(text("""INSERT INTO seats(
                capture_year,program_family,institution_code,choice_code,allocation_lane,
                base_category,is_total,is_ladies,seats,raw_category,raw_allocation_type,
                raw_gender,source_pdf
            ) VALUES (2026,:family,:institution,'CHOICE',:lane,:category,FALSE,FALSE,
                     10,'OPEN','Fixture','G','fixture.pdf')"""), {
                "family": family, "institution": institution, "lane": lane, "category": category,
            })

        refresh(engine, family)

        with engine.connect() as conn:
            runtime = conn.execute(text("""SELECT lowest_rank FROM college_search_runtime
                WHERE program_family=:family AND institution_code=:institution"""), {
                "family": family, "institution": institution,
            }).scalar_one()
            points = conn.execute(text("""SELECT percentile FROM college_search_cutoff_points
                WHERE program_family=:family AND institution_code=:institution ORDER BY percentile"""), {
                "family": family, "institution": institution,
            }).scalars().all()
        assert runtime == 500
        assert points == [70.0, 80.0]

        eligible_75, total_75 = search_college_summary_page(engine, 75.0, family, None, "comp", 1, 10)
        eligible_85, total_85 = search_college_summary_page(engine, 85.0, family, None, "comp", 1, 10)
        eligible_65, total_65 = search_college_summary_page(engine, 65.0, family, None, "comp", 1, 10)
        assert total_75 == 1 and float(eligible_75.iloc[0]["highest_cutoff"]) == 70.0
        assert total_85 == 1 and float(eligible_85.iloc[0]["highest_cutoff"]) == 80.0
        assert total_65 == 0 and eligible_65.empty
    finally:
        with engine.begin() as conn:
            for table in (
                "seat_matrix_runtime", "college_search_cutoff_points", "college_search_runtime",
                "cutoff_college_year_summary", "cutoff_trend_points", "cutoff_filter_options",
            ):
                conn.execute(text(f"DELETE FROM {table} WHERE program_family=:family"), {"family": family})
            conn.execute(text("DELETE FROM seats WHERE institution_code=:institution"), {"institution": institution})
            conn.execute(text("DELETE FROM cutoffs WHERE institution_code=:institution"), {"institution": institution})
            if program_id is not None:
                conn.execute(text("DELETE FROM programs WHERE program_id=:program"), {"program": program_id})
            conn.execute(text("DELETE FROM institutes WHERE institution_code=:institution"), {"institution": institution})
            conn.execute(text("DELETE FROM base_categories WHERE base_code=:code"), {"code": category})
            conn.execute(text("DELETE FROM sections WHERE section_code=:code"), {"code": section})
            conn.execute(text("DELETE FROM stages WHERE stage_code=:code"), {"code": stage})
            conn.execute(text("DELETE FROM allocation_lanes WHERE lane_code=:code"), {"code": lane})
        engine.dispose()


def test_engineering_coverage_does_not_compare_cutoffs_to_another_years_seat_matrix():
    """Historical cutoffs without same-year seats are not false code mismatches."""
    import uuid
    from scripts.db_bootstrap import bootstrap_schema
    from scripts.refresh_derived_data import _engineering_cutoff_seat_coverage

    engine = db()
    bootstrap_schema(engine)
    suffix = uuid.uuid4().hex[:10].upper()
    institution = f"T{suffix}"
    category = f"C{suffix}"
    section = f"S{suffix}"
    stage = f"G{suffix}"
    lane = f"L{suffix}"
    program_name = f"Engineering coverage fixture {suffix}"
    historic_code = f"H{suffix}"
    missing_code = f"M{suffix}"
    matched_code = f"X{suffix}"
    program_id = None

    try:
        with engine.begin() as conn:
            before = _engineering_cutoff_seat_coverage(conn)
            conn.execute(text("INSERT INTO institutes(institution_code,institution_name) VALUES (:code,:name)"),
                         {"code": institution, "name": f"Coverage Fixture {suffix}"})
            program_id = conn.execute(
                text("INSERT INTO programs(program_family,program_name_raw) VALUES ('BE',:name) RETURNING program_id"),
                {"name": program_name},
            ).scalar_one()
            conn.execute(text("INSERT INTO base_categories(base_code) VALUES (:code)"), {"code": category})
            conn.execute(text("INSERT INTO sections(section_code,section_full) VALUES (:code,'Fixture')"), {"code": section})
            conn.execute(text("INSERT INTO stages(stage_code) VALUES (:code)"), {"code": stage})
            conn.execute(text("INSERT INTO allocation_lanes(lane_code,lane_full) VALUES (:code,'Fixture')"), {"code": lane})

            for year, code, rank in ((2025, historic_code, 101), (2026, missing_code, 102), (2026, matched_code, 103)):
                conn.execute(text("""
                    INSERT INTO cutoffs(
                        year,round,institution_code,program_id,program_code,base_category,
                        is_ladies,section_code,stage_code,rank_number,percentile,raw_category,
                        raw_program_name,source_pdf
                    ) VALUES (:year,1,:institution,:program_id,:code,:category,FALSE,
                             :section,:stage,:rank,75.0,'OPEN',:program_name,'fixture.pdf')
                """), {
                    "year": year, "institution": institution, "program_id": program_id,
                    "code": code, "category": category, "section": section,
                    "stage": stage, "rank": rank, "program_name": program_name,
                })

            conn.execute(text("""
                INSERT INTO seats(
                    capture_year,program_family,institution_code,choice_code,allocation_lane,
                    base_category,is_total,is_ladies,seats,raw_category,raw_allocation_type,
                    raw_gender,source_pdf
                ) VALUES (2026,'BE',:institution,:code,:lane,:category,FALSE,FALSE,10,
                         'OPEN','Fixture','G','fixture.pdf')
            """), {"institution": institution, "code": matched_code, "lane": lane, "category": category})

            after = _engineering_cutoff_seat_coverage(conn)
            assert after["unmatched_same_year"] - before["unmatched_same_year"] == 1
            assert after["no_same_year_matrix"] - before["no_same_year_matrix"] == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM seats WHERE institution_code=:institution"), {"institution": institution})
            conn.execute(text("DELETE FROM cutoffs WHERE institution_code=:institution"), {"institution": institution})
            if program_id is not None:
                conn.execute(text("DELETE FROM programs WHERE program_id=:program_id"), {"program_id": program_id})
            conn.execute(text("DELETE FROM institutes WHERE institution_code=:institution"), {"institution": institution})
            conn.execute(text("DELETE FROM base_categories WHERE base_code=:code"), {"code": category})
            conn.execute(text("DELETE FROM sections WHERE section_code=:code"), {"code": section})
            conn.execute(text("DELETE FROM stages WHERE stage_code=:code"), {"code": stage})
            conn.execute(text("DELETE FROM allocation_lanes WHERE lane_code=:code"), {"code": lane})

