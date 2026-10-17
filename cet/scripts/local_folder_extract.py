#!/usr/bin/env python3
"""Run CAPFind's existing PDF extractors over PDFs in local_extraction/input."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
INPUT = BASE / "local_extraction" / "input"
OUTPUT = BASE / "local_extraction" / "output"
READY = BASE / "local_extraction" / "ready_to_upload"
REPORTS = BASE / "local_extraction" / "reports"
CHUNK_EXTRACTOR = BASE / "scripts" / "chunked_cutoff_extractor.py"
SEAT_EXTRACTOR = BASE / "scripts" / "seat_matrix_extractor.py"

def kind_from_name(name: str) -> str | None:
    n = name.lower().replace("-", "_").replace(" ", "_")
    if any(k in n for k in ("seatmatrix", "seat_matrix", "seat_mtx", "_sm", "sm_")):
        return "SEATS"
    if any(k in n for k in ("cutoff", "cut_off", "cap1", "cap2", "cap3", "cap4", "cap_round")):
        return "CUTOFFS"
    return None

def main() -> int:
    ap = argparse.ArgumentParser(description="Extract CAPFind PDFs locally using the existing pipeline.")
    ap.add_argument("--chunk-pages", type=int, default=10, help="Pages per cutoff chunk (default: 10)")
    ap.add_argument("--hybrid", action="store_true", help="Enable OCR fallback in chunked cutoff extraction")
    args = ap.parse_args()
    if not 1 <= args.chunk_pages <= 1000:
        ap.error("--chunk-pages must be between 1 and 1000")
    for folder in (INPUT, OUTPUT, READY, REPORTS):
        folder.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(p for p in INPUT.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"No PDFs found. Copy PDFs into: {INPUT}")
        return 1

    summary = {"started_at": datetime.now().isoformat(timespec="seconds"), "input_folder": str(INPUT),
               "chunk_pages": args.chunk_pages, "files": []}
    failures = 0
    for pdf in pdfs:
        kind = kind_from_name(pdf.name)
        if not kind:
            print(f"SKIP (filename doesn't identify cutoff vs seat matrix): {pdf.name}")
            summary["files"].append({"pdf": pdf.name, "status": "SKIPPED", "error": "Rename file to include cutoff/CAP1-CAP4 or seatmatrix/seat_matrix."})
            failures += 1
            continue
        # Each PDF gets a separate work directory; manifests can never mix source files.
        workdir = OUTPUT / pdf.stem
        workdir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {kind}: {pdf.name} ===", flush=True)
        if kind == "CUTOFFS":
            cmd = [sys.executable, str(CHUNK_EXTRACTOR), str(pdf), "--out", str(workdir),
                   "--chunk-pages", str(args.chunk_pages), "--source-name", pdf.name]
            if args.hybrid:
                cmd.append("--hybrid")
        else:
            cmd = [sys.executable, str(SEAT_EXTRACTOR), str(pdf), "--out", str(workdir)]
        log_path = REPORTS / f"{pdf.stem}.log"
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.run(cmd, cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors="replace")
            log.write(proc.stdout)
        print(proc.stdout[-6000:], flush=True)
        if proc.returncode != 0:
            print(f"FAILED: {pdf.name}; see {log_path}", file=sys.stderr)
            summary["files"].append({"pdf": pdf.name, "kind": kind, "status": "FAILED",
                                     "return_code": proc.returncode, "log": str(log_path)})
            failures += 1
            continue
        suffix = "_cutoffs.csv" if kind == "CUTOFFS" else "_seats_long.csv"
        candidates = sorted(workdir.rglob(f"*{suffix}"))
        candidates = [p for p in candidates if p.name != "ALL_PDFS_cutoffs.csv"]
        if not candidates:
            summary["files"].append({"pdf": pdf.name, "kind": kind, "status": "FAILED",
                                     "error": f"Extractor exited successfully but no {suffix} was found", "log": str(log_path)})
            failures += 1
            continue
        # The chunked cutoff extractor's final canonical artifact is at the workdir root.
        artifact = next((p for p in candidates if p.parent == workdir), candidates[-1])
        target = READY / f"{pdf.stem}{suffix}"
        shutil.copy2(artifact, target)
        # Validate that the CSV has a header and at least one data row before calling it ready.
        with target.open("r", encoding="utf-8-sig", errors="strict") as f:
            header = f.readline().strip()
            first_row = f.readline().strip()
        required = ({"source_pdf", "page", "institution_code", "institution_name", "program_code",
                     "program_name", "status", "home_university", "section", "stage", "category",
                     "rank", "rank_number", "rank_suffix", "percentage", "percentage_raw", "raw_value",
                     "source", "merged_from"} if kind == "CUTOFFS" else
                    {"source_pdf", "page", "institution_code", "choice_code", "allocation_type",
                     "category", "gender", "seats"})
        cols = {x.strip().lstrip("\ufeff") for x in header.split(",")}
        missing = sorted(required - cols)
        if not first_row or missing:
            target.unlink(missing_ok=True)
            summary["files"].append({"pdf": pdf.name, "kind": kind, "status": "FAILED",
                                     "error": "Empty output or missing canonical columns: " + ", ".join(missing),
                                     "artifact": str(artifact), "log": str(log_path)})
            failures += 1
            continue
        summary["files"].append({"pdf": pdf.name, "kind": kind, "status": "READY",
                                 "csv": str(target), "bytes": target.stat().st_size, "log": str(log_path)})
        print(f"READY TO UPLOAD: {target}", flush=True)

    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    summary["status"] = "FAILED" if failures else "COMPLETED"
    report = REPORTS / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nRun report: {report}")
    print(f"Ready CSV folder: {READY}")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
