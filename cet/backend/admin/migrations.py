from .db import connect

def ensure_part4_schema():
    # The PostgreSQL schema is created idempotently at startup. This function
    # remains as a compatibility hook for existing admin publish code.
    with connect() as c:
        c.execute("ALTER TABLE data_releases ADD COLUMN IF NOT EXISTS published_at TIMESTAMP")
        c.execute("ALTER TABLE data_releases ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP")
        c.execute("ALTER TABLE data_releases ADD COLUMN IF NOT EXISTS manifest_json TEXT")
        c.execute("ALTER TABLE data_releases ADD COLUMN IF NOT EXISTS backup_path TEXT")
        c.execute("""CREATE TABLE IF NOT EXISTS cutoff_trend_points (program_family TEXT NOT NULL, institution_code TEXT NOT NULL, program_id INTEGER NOT NULL, base_category TEXT NOT NULL, is_ladies BOOLEAN NOT NULL DEFAULT FALSE, section_code TEXT NOT NULL, year INTEGER NOT NULL, round INTEGER NOT NULL, closing_percentile REAL NOT NULL, closing_rank INTEGER, PRIMARY KEY (program_family,institution_code,program_id,base_category,is_ladies,section_code,year,round))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cutoff_trend_lookup ON cutoff_trend_points(program_family,institution_code,base_category,is_ladies,section_code,year,round)")
        c.execute("""CREATE TABLE IF NOT EXISTS cutoff_college_year_summary (program_family TEXT NOT NULL, institution_code TEXT NOT NULL, year INTEGER NOT NULL, low_percentile REAL NOT NULL, high_percentile REAL NOT NULL, low_rank INTEGER, PRIMARY KEY (program_family,institution_code,year))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cutoff_summary_lookup ON cutoff_college_year_summary(program_family,institution_code,year)")
        c.execute("""CREATE TABLE IF NOT EXISTS cutoff_filter_options (program_family TEXT NOT NULL, institution_code TEXT NOT NULL, is_ladies BOOLEAN NOT NULL DEFAULT FALSE, year INTEGER NOT NULL, base_category TEXT NOT NULL, section_code TEXT NOT NULL, PRIMARY KEY (program_family,institution_code,is_ladies,year,base_category,section_code))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_cutoff_options_lookup ON cutoff_filter_options(program_family,institution_code,is_ladies,year,base_category,section_code)")
        c.execute("""CREATE TABLE IF NOT EXISTS seat_matrix_runtime (program_family TEXT NOT NULL, institution_code TEXT NOT NULL, capture_year INTEGER NOT NULL, choice_code TEXT NOT NULL, allocation_lane TEXT NOT NULL, base_category TEXT NOT NULL, gender_g INTEGER, gender_l INTEGER, category_total INTEGER, is_total BOOLEAN NOT NULL DEFAULT FALSE, PRIMARY KEY (program_family,institution_code,capture_year,choice_code,allocation_lane,base_category,is_total))""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_seat_runtime_lookup ON seat_matrix_runtime(program_family,institution_code,capture_year,choice_code,allocation_lane)")
        c.execute("CREATE TABLE IF NOT EXISTS derived_data_build_jobs (id SERIAL PRIMARY KEY, course_family TEXT, status TEXT NOT NULL DEFAULT 'QUEUED', progress INTEGER NOT NULL DEFAULT 0, message TEXT, started_at TIMESTAMP, finished_at TIMESTAMP, created_by INTEGER, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_derived_build_jobs_created ON derived_data_build_jobs(created_at DESC)")
