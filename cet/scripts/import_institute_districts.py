"""Apply reviewed district assignments from official CET Cell institute references.

Only institute codes explicitly included in the reviewed reference CSV are updated.
Existing conflicting district values are never overwritten.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(ROOT / "data/reference/institute_districts.csv"))
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from src.cet_cap.db import get_engine
    rows = list(csv.DictReader(Path(args.csv).open(encoding="utf-8", newline="")))
    seen = {}
    for row in rows:
        code = row["institution_code"].strip()
        district = row["district"].strip()
        if not code or not district:
            raise ValueError("Every district reference row needs institution_code and district")
        if code in seen and seen[code] != district:
            raise ValueError(f"Conflicting district values for institute {code}")
        seen[code] = district

    engine = get_engine(args.db_url)
    updated = missing = conflicts = unchanged = 0
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE institutes ADD COLUMN IF NOT EXISTS district TEXT"))
        conn.execute(text("ALTER TABLE institutes ADD COLUMN IF NOT EXISTS district_source TEXT"))
        conn.execute(text("ALTER TABLE institutes ADD COLUMN IF NOT EXISTS district_verified_at TIMESTAMP"))
        for row in rows:
            code = row["institution_code"].strip()
            district = row["district"].strip()
            current = conn.execute(
                text("SELECT district FROM institutes WHERE institution_code=:code"),
                {"code": code},
            ).scalar_one_or_none()
            if current is None:
                exists = conn.execute(
                    text("SELECT EXISTS(SELECT 1 FROM institutes WHERE institution_code=:code)"),
                    {"code": code},
                ).scalar_one()
                if not exists:
                    missing += 1
                    continue
            if current and current.strip().lower() != district.lower():
                conflicts += 1
                continue
            if current and current.strip().lower() == district.lower():
                unchanged += 1
                continue
            if args.dry_run:
                updated += 1
                continue
            result = conn.execute(text("""
                UPDATE institutes
                SET district=:district,
                    district_source=:source,
                    district_verified_at=CURRENT_TIMESTAMP
                WHERE institution_code=:code
                  AND (district IS NULL OR btrim(district)='')
            """), {
                "district": district,
                "source": row["source"].strip() + " | " + row["source_url"].strip(),
                "code": code,
            })
            updated += result.rowcount

    print(f"District assignments {'would update' if args.dry_run else 'updated'}: {updated}")
    print(f"Already correct: {unchanged}")
    print(f"Missing institute codes: {missing}")
    print(f"Conflicting existing districts (not overwritten): {conflicts}")


if __name__ == "__main__":
    main()
