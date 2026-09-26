from .db import connect

def ensure_part4_schema():
    # The PostgreSQL schema is created idempotently at startup. This function
    # remains as a compatibility hook for existing admin publish code.
    with connect() as c:
        c.execute("ALTER TABLE data_releases ADD COLUMN IF NOT EXISTS published_at TIMESTAMP")
        c.execute("ALTER TABLE data_releases ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP")
        c.execute("ALTER TABLE data_releases ADD COLUMN IF NOT EXISTS manifest_json TEXT")
        c.execute("ALTER TABLE data_releases ADD COLUMN IF NOT EXISTS backup_path TEXT")
