"""Refresh precomputed PostgreSQL runtime data used by the public portal.

Raw tables (cutoffs/seats) remain authoritative. These derived tables are
rebuilt after an approved publication so public requests only perform small
indexed lookups.
"""
from __future__ import annotations

import argparse
import os
from sqlalchemy import text
from src.cet_cap.db import get_engine

ZERO_FILTER = "NOT (c.rank_number = 0 AND c.percentile = 0.0)"


def refresh(engine, course_family: str | None = None) -> None:
    course_where = " AND p.program_family = :course" if course_family else ""
    seat_where = " WHERE s.program_family = :course" if course_family else ""
    params = {"course": course_family} if course_family else {}
    with engine.begin() as conn:
        source_cutoffs = conn.execute(text(f"""
            SELECT COUNT(*)
            FROM cutoffs c
            JOIN programs p ON p.program_id = c.program_id
            WHERE {"p.program_family = :course" if course_family else "TRUE"}
        """), params).scalar_one()
        source_seats = conn.execute(text(f"""
            SELECT COUNT(*) FROM seats s
            WHERE {"s.program_family = :course" if course_family else "TRUE"}
        """), params).scalar_one()
        if source_cutoffs == 0 or source_seats == 0:
            scope = f"course {course_family}" if course_family else "the production database"
            raise RuntimeError(f"Refusing to rebuild derived data: source data is incomplete for {scope} (cutoffs={source_cutoffs}, seats={source_seats})")

        if course_family:
            conn.execute(text("DELETE FROM cutoff_trend_points WHERE program_family = :course"), params)
            conn.execute(text("DELETE FROM cutoff_college_year_summary WHERE program_family = :course"), params)
            conn.execute(text("DELETE FROM cutoff_filter_options WHERE program_family = :course"), params)
            conn.execute(text("DELETE FROM seat_matrix_runtime WHERE program_family = :course"), params)
        else:
            conn.execute(text("TRUNCATE cutoff_trend_points, cutoff_college_year_summary, cutoff_filter_options, seat_matrix_runtime"))

        conn.execute(text(f"""
            INSERT INTO cutoff_trend_points
            (program_family, institution_code, program_id, base_category,
             is_ladies, section_code, year, round, closing_percentile, closing_rank)
            SELECT p.program_family, c.institution_code, c.program_id,
                   c.base_category, c.is_ladies, c.section_code,
                   c.year, c.round,
                   MIN(c.percentile) AS closing_percentile,
                   (ARRAY_AGG(c.rank_number ORDER BY c.percentile ASC NULLS LAST, c.rank_number DESC))[1] AS closing_rank
            FROM cutoffs c
            JOIN programs p ON p.program_id = c.program_id
            WHERE {ZERO_FILTER} AND c.is_ladies = FALSE{course_where}
            GROUP BY p.program_family, c.institution_code, c.program_id,
                     c.base_category, c.is_ladies, c.section_code,
                     c.year, c.round
        """), params)

        conn.execute(text(f"""
            INSERT INTO cutoff_college_year_summary
            (program_family, institution_code, year, low_percentile,
             high_percentile, low_rank)
            SELECT p.program_family, c.institution_code, c.year,
                   MIN(c.percentile),
                   MAX(c.percentile),
                   (ARRAY_AGG(c.rank_number ORDER BY c.percentile ASC NULLS LAST,
                              c.rank_number DESC))[1]
            FROM cutoffs c
            JOIN programs p ON p.program_id = c.program_id
            WHERE {ZERO_FILTER}{course_where}
            GROUP BY p.program_family, c.institution_code, c.year
        """), params)

        conn.execute(text(f"""
            INSERT INTO cutoff_filter_options
            (program_family, institution_code, is_ladies, year,
             base_category, section_code)
            SELECT DISTINCT p.program_family, c.institution_code,
                   FALSE AS is_ladies, c.year, c.base_category, c.section_code
            FROM cutoffs c
            JOIN programs p ON p.program_id = c.program_id
            WHERE {ZERO_FILTER} AND c.is_ladies = FALSE{course_where}
        """), params)

        conn.execute(text(f"""
            INSERT INTO seat_matrix_runtime
            (program_family, institution_code, capture_year, choice_code,
             allocation_lane, base_category, gender_g, gender_l,
             category_total, is_total)
            SELECT
                s.program_family, s.institution_code, s.capture_year,
                s.choice_code, s.allocation_lane,
                COALESCE(s.base_category, 'Total') AS base_category,
                MAX(CASE WHEN s.is_ladies = FALSE AND s.is_total = FALSE
                         THEN s.seats END) AS gender_g,
                MAX(CASE WHEN s.is_ladies = TRUE AND s.is_total = FALSE
                         THEN s.seats END) AS gender_l,
                MAX(CASE WHEN s.is_total = TRUE OR s.is_ladies IS NULL THEN s.seats END) AS category_total,
                BOOL_OR(s.is_total)
            FROM seats s
            JOIN (
                SELECT institution_code, program_family, MAX(capture_year) AS capture_year
                FROM seats
                GROUP BY institution_code, program_family
            ) latest
              ON latest.institution_code = s.institution_code
             AND latest.program_family = s.program_family
             AND latest.capture_year = s.capture_year
            {seat_where}
            GROUP BY s.program_family, s.institution_code, s.capture_year,
                     s.choice_code, s.allocation_lane,
                     COALESCE(s.base_category, 'Total')
        """), params)

        derived_counts = conn.execute(text("""
            SELECT
              (SELECT COUNT(*) FROM cutoff_trend_points WHERE (:course IS NULL OR program_family = :course)) AS trend_count,
              (SELECT COUNT(*) FROM cutoff_filter_options WHERE (:course IS NULL OR program_family = :course)) AS filter_count,
              (SELECT COUNT(*) FROM seat_matrix_runtime WHERE (:course IS NULL OR program_family = :course)) AS seat_count
        """), {"course": course_family}).mappings().one()
        if min(derived_counts.values()) <= 0:
            raise RuntimeError(f"Derived-data validation failed: {dict(derived_counts)}")

        # Seat matrices are derived cache data, so validate coverage against the
        # authoritative seats table for EVERY course and EVERY institution.
        # A partial runtime rebuild must never be published as if it were valid.
        seat_validation = conn.execute(text("""
            WITH latest AS (
                SELECT institution_code, program_family, MAX(capture_year) AS capture_year
                FROM seats
                WHERE (:course IS NULL OR program_family = :course)
                GROUP BY institution_code, program_family
            ),
            source_groups AS (
                SELECT s.program_family, s.institution_code, s.capture_year,
                       COUNT(DISTINCT (s.choice_code, s.allocation_lane,
                                       COALESCE(s.base_category, 'Total'), s.is_total)) AS groups
                FROM seats s
                JOIN latest l
                  ON l.institution_code = s.institution_code
                 AND l.program_family = s.program_family
                 AND l.capture_year = s.capture_year
                GROUP BY s.program_family, s.institution_code, s.capture_year
            ),
            runtime_groups AS (
                SELECT program_family, institution_code, capture_year,
                       COUNT(DISTINCT (choice_code, allocation_lane, base_category, is_total)) AS groups,
                       COUNT(*) FILTER (
                           WHERE gender_g IS NULL AND gender_l IS NULL AND category_total IS NULL
                       ) AS empty_rows
                FROM seat_matrix_runtime
                WHERE (:course IS NULL OR program_family = :course)
                GROUP BY program_family, institution_code, capture_year
            )
            SELECT COUNT(*) FILTER (
                       WHERE r.institution_code IS NULL
                          OR r.capture_year <> s.capture_year
                          OR r.groups < s.groups
                          OR r.empty_rows > 0
                   ) AS invalid_institutions,
                   COUNT(*) AS source_institutions
            FROM source_groups s
            LEFT JOIN runtime_groups r
              ON r.program_family = s.program_family
             AND r.institution_code = s.institution_code
             AND r.capture_year = s.capture_year
        """), {"course": course_family}).mappings().one()
        if int(seat_validation["invalid_institutions"] or 0) > 0:
            raise RuntimeError(
                "Seat-matrix validation failed: "
                f"{seat_validation['invalid_institutions']} of "
                f"{seat_validation['source_institutions']} institutions have incomplete runtime data"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build PostgreSQL derived data for the public Slide 2 UI.")
    parser.add_argument("--course", default=None, help="Optional program family to rebuild, e.g. BBA.")
    parser.add_argument("--job-id", type=int, default=None, help="Admin derived-data build job id.")
    args = parser.parse_args()
    engine = get_engine(os.getenv("DATABASE_URL"))
    refresh(engine, args.course)
    print("Derived public runtime data refreshed successfully.")


if __name__ == "__main__":
    main()
