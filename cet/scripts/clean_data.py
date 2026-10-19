"""
clean_data.py — Cleans raw cutoff CSVs so validate_data.py comes back exit 0.

What it does (only two real problems exist in the data, per the validate_data.py run):
  1. Rows with a genuinely BLANK category (rank/percentage present, category lost
     upstream in PDF extraction) cannot be repaired here — there is no category to
     recover. They are QUARANTINED to data/processed/rejects/<file>_rejects.csv
     with a reason, and dropped from the cleaned output. Nothing is invented.
  2. Bare "PWD" (no OPEN/SC/... sub-code, no H/O/S suffix) IS a real, valid
     category in this dataset — it was just missing from category_whitelist.csv.
     Fix applied at the reference-data level: add PWD as a first-class base
     category. No row is touched for this one; the taxonomy was wrong, not the data.

Run: python scripts/clean_data.py data/raw/ data/processed/
Only operates on files that match the cutoffs schema (same REQUIRED_COLUMNS as
validate_data.py) — seat-matrix files are a different table and are skipped,
not "fixed", since there is nothing wrong with them relative to this schema.
"""

import sys
import csv
from pathlib import Path


REQUIRED_COLUMNS = [
    'source_pdf', 'page', 'institution_code', 'institution_name',
    'program_code', 'program_name', 'status', 'home_university',
    'section', 'stage', 'category', 'rank', 'rank_number',
    'rank_suffix', 'percentage', 'percentage_raw', 'raw_value',
    'source', 'merged_from',
]

CATEGORY_WHITELIST_PATH = Path('data/reference/category_whitelist.csv')


def ensure_pwd_in_whitelist():
    """Add bare PWD as a valid base category without loading pandas."""
    path = CATEGORY_WHITELIST_PATH
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)  # Reference whitelist is small; cutoff CSVs are not.
    if "base_code" not in fieldnames:
        raise ValueError(f"Whitelist is missing base_code column: {path}")
    if any(row.get("base_code", "") == "PWD" for row in rows):
        return False
    if not fieldnames:
        raise ValueError(f"Whitelist has no header: {path}")
    rows.append({"base_code": "PWD", "category_full": "Persons with Disability (unspecified sub-category)", "category_group": "Special"})
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return True


def clean_file(path: Path, out_dir: Path, rejects_dir: Path):
    """Stream a cutoff CSV row by row to keep peak memory independent of file size.

    Outputs are first written to temporary files and atomically replaced only after
    the complete input has been read. If processing fails, previous output files
    remain intact and incomplete temporary files are removed.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rejects_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / path.name
    reject_path = rejects_dir / f"{path.stem}_rejects.csv"
    out_tmp = out_path.with_name(out_path.name + ".tmp")
    reject_tmp = reject_path.with_name(reject_path.name + ".tmp")
    rows_in = rows_kept = rows_quarantined = 0

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            fieldnames = list(reader.fieldnames or [])
            if any(column not in fieldnames for column in REQUIRED_COLUMNS):
                print(f"  SKIP (not a cutoffs-schema file): {path.name}")
                return None

            with out_tmp.open("w", encoding="utf-8", newline="") as clean_stream, \
                    reject_tmp.open("w", encoding="utf-8", newline="") as reject_stream:
                clean_writer = csv.DictWriter(clean_stream, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
                reject_fields = fieldnames + ["reject_reason"]
                reject_writer = csv.DictWriter(reject_stream, fieldnames=reject_fields, quoting=csv.QUOTE_MINIMAL)
                clean_writer.writeheader()
                reject_writer.writeheader()
                for row in reader:
                    rows_in += 1
                    if not (row.get("category") or "").strip():
                        row["reject_reason"] = "blank_category_upstream_pdf_extraction"
                        reject_writer.writerow(row)
                        rows_quarantined += 1
                    else:
                        clean_writer.writerow(row)
                        rows_kept += 1

        out_tmp.replace(out_path)
        if rows_quarantined:
            reject_tmp.replace(reject_path)
        else:
            reject_tmp.unlink(missing_ok=True)
            reject_path.unlink(missing_ok=True)
        return {"file": path.name, "rows_in": rows_in, "rows_kept": rows_kept,
                "rows_quarantined": rows_quarantined,
                "reject_path": str(reject_path) if rows_quarantined else None}
    except Exception:
        out_tmp.unlink(missing_ok=True)
        reject_tmp.unlink(missing_ok=True)
        raise


def main(raw_dir: str, out_dir: str):
    raw = Path(raw_dir)
    out = Path(out_dir)
    rejects = out / 'rejects'

    added_pwd = ensure_pwd_in_whitelist()
    print(f'category_whitelist.csv: {"added PWD as a valid base category" if added_pwd else "PWD already present"}\n')

    results = []
    for path in sorted(raw.glob('*.csv')):
        r = clean_file(path, out, rejects)
        if r:
            results.append(r)

    print(f"{'FILE':<30}{'IN':>8}{'KEPT':>8}{'QUARANTINED':>14}")
    print('-' * 60)
    for r in results:
        print(f"{r['file']:<30}{r['rows_in']:>8}{r['rows_kept']:>8}{r['rows_quarantined']:>14}")
        if r['reject_path']:
            print(f"   -> quarantined rows written to {r['reject_path']}")


if __name__ == '__main__':
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/raw/'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'data/processed/'
    main(raw_dir, out_dir)
