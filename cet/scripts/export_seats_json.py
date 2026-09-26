"""
Build the public seat-matrix runtime from the authoritative approved PostgreSQL database.

The publisher must never rebuild public seats from an older extracted CSV.
The `seats` table is the source of truth after an import is approved.  For each
course/institution we export only the most recent capture_year, matching the
public API's seat-matrix semantics.  The output is compact and shaped for the
existing front-end renderer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

COURSES = ["BBA", "BCA", "MBA", "MCA"]
ALLOC_ORDER = ["State Level", "HU", "OHU", "PWD", "DEF"]
CATEGORY_ORDER = ["OPEN", "SC", "ST", "VJDT", "VJ/DT", "NTB", "NTC", "NTD", "OBC", "SEBC", "EWS", "Total"]


def category_sort_key(cat: str) -> int:
    try:
        return CATEGORY_ORDER.index(cat)
    except ValueError:
        return len(CATEGORY_ORDER)


def alloc_sort_key(alloc: str) -> int:
    try:
        return ALLOC_ORDER.index(alloc)
    except ValueError:
        return len(ALLOC_ORDER)


def export_course(conn, course: str) -> dict:
    """institution_code -> choice_code -> allocation_type -> category rows."""
    # Use the latest capture snapshot independently for each institution.
    # This mirrors seat_matrix_for_institute() in src/cet_cap/queries.py and
    # prevents older years from being mixed into current capacity.
    rows = conn.execute(
        """
        SELECT institution_code, choice_code,
               raw_allocation_type, raw_category, raw_gender, seats
        FROM seats s
        WHERE program_family = ?
          AND capture_year = (
              SELECT MAX(s2.capture_year)
              FROM seats s2
              WHERE s2.institution_code = s.institution_code
                AND s2.program_family = s.program_family
          )
        ORDER BY institution_code, choice_code, allocation_lane,
                 is_total, base_category, raw_category, raw_gender
        """,
        (course,),
    ).fetchall()

    out: dict = {}
    for inst, choice, allocation, category, gender, seats in rows:
        inst = str(inst).strip()
        choice = str(choice).strip()
        allocation = str(allocation).strip()
        category = str(category).strip()
        gender = str(gender or "").strip()
        if not inst or not choice or not allocation:
            continue

        out.setdefault(inst, {})
        out[inst].setdefault(choice, {})
        out[inst][choice].setdefault(allocation, {})
        bucket = out[inst][choice][allocation].setdefault(
            category, {"category": category, "G": None, "L": None, "total": None}
        )

        if category == "Total":
            bucket["total"] = int(seats)
        elif gender == "G":
            bucket["G"] = int(seats)
        elif gender == "L":
            bucket["L"] = int(seats)
        elif not gender:
            bucket["total"] = int(seats)

    result: dict = {}
    for inst, choices in out.items():
        result[inst] = {}
        for choice, allocs in choices.items():
            ordered_allocs = {}
            for allocation in sorted(allocs, key=alloc_sort_key):
                ordered_allocs[allocation] = sorted(
                    allocs[allocation].values(),
                    key=lambda r: category_sort_key(r["category"]),
                )
            result[inst][choice] = ordered_allocs
    return result


def export_from_db(db_url: str | None, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    from pg_runtime import open_cursor
    db_conn, conn = open_cursor(db_url)
    try:
        result = {}
        for course in COURSES:
            data = export_course(conn, course)
            if not data:
                continue
            result[course] = data
            payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            (out_dir / f"seats_{course}.json").write_text(payload, encoding="utf-8")
            (out_dir / f"seats_{course}.js").write_text(
                "window.__SEAT_DATA__ = window.__SEAT_DATA__ || {};\n"
                f"window.__SEAT_DATA__['{course}'] = {payload};\n",
                encoding="utf-8",
            )
            print(f"{course}: {len(data)} institutes -> seats_{course}.json / .js")
        return result
    finally:
        db_conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db-url", default=None, help="PostgreSQL DATABASE_URL (defaults to environment)")
    ap.add_argument("--out", default="site/data")
    # Kept only as a compatibility guard: old callers must fail loudly rather
    # than silently falling back to stale raw CSV data.
    ap.add_argument("--raw", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.raw:
        raise SystemExit("--raw is no longer supported; publish always reads PostgreSQL.")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_from_db(args.db_url, out_dir)


if __name__ == "__main__":
    main()
