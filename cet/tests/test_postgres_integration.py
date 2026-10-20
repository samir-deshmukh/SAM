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
            conn.execute(text("INSERT INTO institutes(institution_code,institution_name,city) VALUES (:code,:name,'Amravati')"), {"code": code, "name": name})
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
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM cutoff_college_year_summary WHERE institution_code=:code"), {"code": code})
            conn.execute(text("DELETE FROM cutoffs WHERE institution_code=:code"), {"code": code})
            if program_id is not None:
                conn.execute(text("DELETE FROM programs WHERE program_id=:program_id"), {"program_id": program_id})
            conn.execute(text("DELETE FROM institutes WHERE institution_code=:code"), {"code": code})
            conn.execute(text("DELETE FROM base_categories WHERE base_code=:category"), {"category": f"T{suffix}"})
            conn.execute(text("DELETE FROM sections WHERE section_code=:section"), {"section": f"S{suffix}"})
            conn.execute(text("DELETE FROM stages WHERE stage_code=:stage"), {"stage": f"ST{suffix}"})
        api.invalidate_public_caches()
