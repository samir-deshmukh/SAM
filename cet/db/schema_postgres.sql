-- CET CAP Decision Support — PostgreSQL Schema
-- Compatible with PostgreSQL 13+ (Local PostgreSQL, Neon, Supabase, RDS)

-- ============================================================
-- REFERENCE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS institutes (
    institution_code   TEXT PRIMARY KEY,
    institution_name   TEXT NOT NULL,
    home_university    TEXT,
    institute_type     TEXT,
    affiliation_status TEXT,
    city               TEXT,
    district           TEXT,
    address            TEXT,
    website            TEXT,
    city_source        TEXT,
    website_source     TEXT,
    address_source     TEXT,
    verified_at        TIMESTAMP,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS programs (
    program_id         SERIAL PRIMARY KEY,
    program_family     TEXT NOT NULL,
    program_name_raw   TEXT NOT NULL,
    level              TEXT,
    UNIQUE(program_family, program_name_raw)
);

CREATE TABLE IF NOT EXISTS base_categories (
    base_code      TEXT PRIMARY KEY,
    category_full  TEXT,
    category_group TEXT
);

CREATE TABLE IF NOT EXISTS sections (
    section_code TEXT PRIMARY KEY,
    section_full TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stages (
    stage_code TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS allocation_lanes (
    lane_code TEXT PRIMARY KEY,
    lane_full TEXT NOT NULL
);

-- ============================================================
-- FACT TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS cutoffs (
    id               SERIAL PRIMARY KEY,
    year             INTEGER NOT NULL,
    round            INTEGER NOT NULL,
    institution_code TEXT NOT NULL REFERENCES institutes(institution_code),
    program_id       INTEGER NOT NULL REFERENCES programs(program_id),
    base_category    TEXT NOT NULL REFERENCES base_categories(base_code),
    is_ladies        BOOLEAN NOT NULL DEFAULT FALSE,
    section_code     TEXT NOT NULL REFERENCES sections(section_code),
    stage_code       TEXT NOT NULL REFERENCES stages(stage_code),
    home_university  TEXT,
    rank_number      INTEGER,
    rank_suffix      TEXT,
    percentile       REAL NOT NULL,
    raw_category     TEXT NOT NULL,
    raw_program_name TEXT NOT NULL,
    source_pdf       TEXT NOT NULL,
    source_page      INTEGER,
    ingested_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, round, institution_code, program_id,
           base_category, is_ladies, section_code, stage_code,
           rank_number, percentile)
);

CREATE INDEX IF NOT EXISTS idx_cutoffs_filter
    ON cutoffs(year, round, program_id, base_category,
               is_ladies, section_code);

CREATE INDEX IF NOT EXISTS idx_cutoffs_inst_prog
    ON cutoffs(institution_code, program_id);

CREATE INDEX IF NOT EXISTS idx_cutoffs_percentile
    ON cutoffs(percentile DESC);

CREATE TABLE IF NOT EXISTS seats (
    id                  SERIAL PRIMARY KEY,
    capture_year        INTEGER NOT NULL,
    program_family      TEXT NOT NULL,
    institution_code    TEXT NOT NULL REFERENCES institutes(institution_code),
    choice_code         TEXT NOT NULL,
    allocation_lane     TEXT NOT NULL REFERENCES allocation_lanes(lane_code),
    base_category       TEXT REFERENCES base_categories(base_code),
    is_total            BOOLEAN NOT NULL DEFAULT FALSE,
    is_ladies           BOOLEAN,
    seats               INTEGER NOT NULL,
    raw_category        TEXT NOT NULL,
    raw_allocation_type TEXT NOT NULL,
    raw_gender          TEXT NOT NULL DEFAULT '',
    source_pdf          TEXT NOT NULL,
    source_page         INTEGER,
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(capture_year, program_family, institution_code, choice_code,
           allocation_lane, raw_category, raw_gender)
);

CREATE INDEX IF NOT EXISTS idx_seats_lookup
    ON seats(institution_code, choice_code, capture_year);

CREATE INDEX IF NOT EXISTS idx_seats_category
    ON seats(base_category, allocation_lane, is_total);

-- ============================================================
-- STAGING & AUDIT TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS staging_cutoffs (
    id          SERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    raw_row     TEXT NOT NULL,
    loaded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed   BOOLEAN DEFAULT FALSE,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS ingest_log (
    id             SERIAL PRIMARY KEY,
    source_file    TEXT NOT NULL,
    rows_read      INTEGER,
    rows_inserted  INTEGER,
    rows_skipped   INTEGER,
    rows_duplicate INTEGER DEFAULT 0,
    rows_failed    INTEGER,
    ingested_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingest_errors (
    id           SERIAL PRIMARY KEY,
    source_file  TEXT NOT NULL,
    source_page  INTEGER,
    source_row   INTEGER,
    raw_category TEXT,
    raw_program  TEXT,
    reason       TEXT,
    ingested_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_seats (
    id          SERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    raw_row     TEXT NOT NULL,
    loaded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed   BOOLEAN DEFAULT FALSE,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS seats_ingest_log (
    id             SERIAL PRIMARY KEY,
    source_file    TEXT NOT NULL,
    rows_read      INTEGER,
    rows_inserted  INTEGER,
    rows_skipped   INTEGER,
    rows_duplicate INTEGER DEFAULT 0,
    rows_failed    INTEGER,
    ingested_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seats_ingest_errors (
    id                  SERIAL PRIMARY KEY,
    source_file         TEXT NOT NULL,
    source_page         INTEGER,
    institution_code    TEXT,
    choice_code         TEXT,
    raw_allocation_type TEXT,
    raw_category        TEXT,
    reason              TEXT,
    ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
