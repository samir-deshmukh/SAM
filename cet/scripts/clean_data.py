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
    """Add bare PWD as a valid base category if it's not already there."""
    # This reference table is tiny; use csv to avoid importing pandas just for it.
    rows = []
    with CATEGORY_WHITELIST_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if any(str(row.get("base_code", "")).strip().upper() == "PWD" for row in rows):
        return False
    if not fields:
        fields = ["base_code", "category_full", "category_group"]
    rows.append({
        "base_code": "PWD",
        "category_full": "Persons with Disability (unspecified sub-category)",
        "category_group": "Special",
    })
    with CATEGORY_WHITELIST_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return True


def clean_file(path: Path, out_dir: Path, rejects_dir: Path):
    """Stream rows to clean/reject CSVs without materializing the whole file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rejects_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / path.name
    reject_path = rejects_dir / f"{path.stem}_rejects.csv"
    rows_in = rows_kept = rows_quarantined = 0

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fields = list(reader.fieldnames or [])
        if any(c not in fields for c in REQUIRED_COLUMNS):
            print(f"  SKIP (not a cutoffs-schema file): {path.name}")
            return None

        with out_path.open("w", encoding="utf-8-sig", newline="") as clean_handle, reject_path.open("w", encoding="utf-8-sig", newline="") as reject_handle:
            clean_writer = csv.DictWriter(clean_handle, fieldnames=fields, extrasaction="ignore")
            reject_writer = csv.DictWriter(reject_handle, fieldnames=fields + ["reject_reason"], extrasaction="ignore")
            clean_writer.writeheader()
            reject_writer.writeheader()
            for row in reader:
                rows_in += 1
                if not str(row.get("category", "")).strip():
                    rejected = dict(row)
                    rejected["reject_reason"] = "blank_category_upstream_pdf_extraction"
                    reject_writer.writerow(rejected)
                    rows_quarantined += 1
                else:
                    clean_writer.writerow(row)
                    rows_kept += 1

    if rows_quarantined == 0:
        reject_path.unlink(missing_ok=True)
        reject_value = None
    else:
        reject_value = str(reject_path)
    return {
        "file": path.name,
        "rows_in": rows_in,
        "rows_kept": rows_kept,
        "rows_quarantined": rows_quarantined,
        "reject_path": reject_value,
    }

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
