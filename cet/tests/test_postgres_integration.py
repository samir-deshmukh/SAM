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
