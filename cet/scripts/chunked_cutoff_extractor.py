#!/usr/bin/env python3
"""Memory-bounded, resumable cutoff PDF extraction by page-range chunks.

The original PDF is never modified or split. Each page range is extracted
independently from the source file, then validated and streamed into combined
artifacts with original page numbers and source provenance preserved.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
EXTRACTOR = Path(__file__).with_name("cutoff_extractor.py")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def iter_json_array(path: Path):
    """Yield array items incrementally, bounding memory to one JSON object."""
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as stream:
        buffer = stream.read(65536)
        eof = not buffer
        started = False
        while True:
            buffer = buffer.lstrip()
            if not started:
                if not buffer:
                    if eof:
                        raise ValueError(f"Empty JSON array: {path}")
                    buffer = stream.read(65536)
                    eof = not buffer
                    continue
                if not buffer.startswith("["):
                    raise ValueError(f"Expected JSON array: {path}")
                buffer = buffer[1:]
                started = True
                continue

            buffer = buffer.lstrip()
            if not buffer:
                if eof:
                    raise ValueError(f"Unterminated JSON array: {path}")
                buffer = stream.read(65536)
                eof = not buffer
                continue
            if buffer.startswith("]"):
                return
            if buffer.startswith(","):
                buffer = buffer[1:]
                continue
            try:
                item, consumed = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                if eof:
                    raise
                buffer += stream.read(65536)
                eof = not buffer
                continue
            yield item
            buffer = buffer[consumed:]


def split_pdf(source, destination: Path, start: int, end: int) -> None:
    """Legacy helper retained for tests; production extraction no longer splits PDFs."""
    import fitz
    chunk = fitz.open()
    try:
        chunk.insert_pdf(source, from_page=start, to_page=end - 1, links=True, annots=True)
        chunk.save(destination, garbage=3, deflate=True)
    finally:
        chunk.close()


def remap_chunk_artifacts(chunk_out: Path, chunk_stem: str, source_name: str,
                          page_offset: int) -> tuple[Path, Path, Path, int]:
    csv_path = chunk_out / f"{chunk_stem}_cutoffs.csv"
    json_path = chunk_out / f"{chunk_stem}_cutoffs.json"
    audit_path = chunk_out / f"{chunk_stem}_page_audit.json"
    if not (csv_path.is_file() and json_path.is_file() and audit_path.is_file()):
        raise RuntimeError(f"Extractor did not create all expected artifacts for {chunk_stem}")

    tmp_csv = csv_path.with_suffix(".csv.tmp")
    row_count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fin, \
         tmp_csv.open("w", encoding="utf-8-sig", newline="") as fout:
        reader = csv.DictReader(fin)
        fields = reader.fieldnames or []
        writer = csv.DictWriter(fout, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            row["source_pdf"] = source_name
            page = str(row.get("page", "")).strip()
            if page.isdigit():
                row["page"] = str(int(page) + page_offset)
            writer.writerow(row)
            row_count += 1
    tmp_csv.replace(csv_path)

    rows = json.loads(json_path.read_text(encoding="utf-8"))
    for row in rows:
        row["source_pdf"] = source_name
        try:
            row["page"] = int(row["page"]) + page_offset
        except (KeyError, TypeError, ValueError):
            raise RuntimeError(f"Invalid page value in {json_path}")
    atomic_json(json_path, rows)

    audits = json.loads(audit_path.read_text(encoding="utf-8"))
    for audit in audits:
        audit["page"] = int(audit["page"]) + page_offset
    atomic_json(audit_path, audits)
    return csv_path, json_path, audit_path, row_count



def validate_chunk_artifacts(chunk_out: Path, artifact_stem: str, source_name: str,
                             start_page: int, end_page: int) -> tuple[Path, Path, Path, int]:
    """Validate a source-page-range extraction without rewriting its artifacts."""
    csv_path = chunk_out / f"{artifact_stem}_cutoffs.csv"
    json_path = chunk_out / f"{artifact_stem}_cutoffs.json"
    audit_path = chunk_out / f"{artifact_stem}_page_audit.json"
    if not (csv_path.is_file() and json_path.is_file() and audit_path.is_file()):
        raise RuntimeError(f"Extractor did not create all expected artifacts for {artifact_stem}")

    csv_count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fin:
        csv_rows = iter(csv.DictReader(fin))
        json_rows = iter_json_array(json_path)
        sentinel = object()
        while True:
            csv_row = next(csv_rows, sentinel)
            json_row = next(json_rows, sentinel)
            if csv_row is sentinel and json_row is sentinel:
                break
            if csv_row is sentinel or json_row is sentinel:
                raise RuntimeError(f"CSV/JSON row-count mismatch in {artifact_stem}")
            try:
                csv_page = int(csv_row.get("page", ""))
                json_page = int(json_row.get("page", 0))
            except (AttributeError, TypeError, ValueError):
                raise RuntimeError(f"Invalid page value in {artifact_stem}")
            if not start_page <= csv_page <= end_page or csv_page != json_page:
                raise RuntimeError(f"CSV/JSON page mismatch in {artifact_stem}")
            if csv_row.get("source_pdf") != source_name or json_row.get("source_pdf") != source_name:
                raise RuntimeError(f"Source provenance mismatch in {artifact_stem}")
            for field, csv_value in csv_row.items():
                json_value = json_row.get(field)
                if isinstance(json_value, list):
                    json_value = ", ".join(str(value) for value in json_value)
                expected_value = "" if json_value is None else str(json_value)
                if csv_value != expected_value:
                    raise RuntimeError(f"CSV/JSON data mismatch in {artifact_stem}, page {csv_page}, field {field}")
            csv_count += 1

    expected_page = start_page
    for audit in iter_json_array(audit_path):
        if int(audit.get("page", 0)) != expected_page:
            raise RuntimeError(f"Page-audit coverage mismatch in {audit_path}; expected page {expected_page}")
        expected_page += 1
    if expected_page != end_page + 1:
        raise RuntimeError(f"Page-audit coverage mismatch in {audit_path}; ended at page {expected_page - 1}")
    return csv_path, json_path, audit_path, csv_count

def combine_outputs(outdir: Path, source: Path, parts: list[dict], total_pages: int, source_hash: str) -> dict:
    final_csv = outdir / f"{source.stem}_cutoffs.csv"
    final_json = outdir / f"{source.stem}_cutoffs.json"
    final_audit = outdir / f"{source.stem}_page_audit.json"
    csv_tmp = final_csv.with_suffix(".csv.tmp")
    json_tmp = final_json.with_suffix(".json.tmp")
    total_rows = 0
    audit_count = 0

    with csv_tmp.open("w", encoding="utf-8-sig", newline="") as fout:
        writer = None
        for part in parts:
            part_csv = outdir / part["csv"]
            with part_csv.open("r", encoding="utf-8-sig", newline="") as fin:
                reader = csv.DictReader(fin)
                if writer is None:
                    writer = csv.DictWriter(fout, fieldnames=reader.fieldnames or [])
                    writer.writeheader()
                for row in reader:
                    writer.writerow(row)
                    total_rows += 1
    if writer is None:
        raise RuntimeError("No chunk CSVs available to combine")
    csv_tmp.replace(final_csv)

    with json_tmp.open("w", encoding="utf-8") as fout:
        fout.write("[\n")
        first = True
        for part in parts:
            part_json = outdir / part["json"]
            for row in iter_json_array(part_json):
                if not first:
                    fout.write(",\n")
                json.dump(row, fout, ensure_ascii=False)
                first = False
        fout.write("\n]\n")
    json_tmp.replace(final_json)

    audit_tmp = final_audit.with_suffix(".json.tmp")
    expected_page = 1
    with audit_tmp.open("w", encoding="utf-8") as fout:
        fout.write("[\n")
        first = True
        for part in parts:
            part_audit = outdir / part["audit"]
            for audit in iter_json_array(part_audit):
                page = int(audit["page"])
                if page != expected_page:
                    audit_tmp.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"Page audit coverage mismatch: expected page {expected_page}, got {page}"
                    )
                if not first:
                    fout.write(",\n")
                json.dump(audit, fout, ensure_ascii=False)
                first = False
                expected_page += 1
                audit_count += 1
        fout.write("\n]\n")
    if expected_page != total_pages + 1:
        audit_tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Page audit coverage mismatch: expected pages 1..{total_pages}; "
            f"got {audit_count} entries"
        )
    audit_tmp.replace(final_audit)
    return {
        "source_pdf": str(source),
        "source_sha256": source_hash,
        "total_pages": total_pages,
        "chunk_count": len(parts),
        "chunk_pages": sorted({p["page_count"] for p in parts}),
        "rows_extracted": total_rows,
        "page_audit_entries": audit_count,
        "csv": str(final_csv),
        "json": str(final_json),
        "page_audit": str(final_audit),
        "page_coverage_valid": True,
    }


def main() -> int:
    # Yield CPU scheduling priority to the web/API process on small shared instances.
    # The nested cutoff extractor inherits this lower priority. This does not change
    # correctness or concurrency; it helps keep admin requests responsive during imports.
    try:
        os.nice(5)
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-name", default=None, help="Original uploaded filename for provenance fields")
    parser.add_argument("--chunk-pages", type=int, default=1000,
                        help="Maximum source pages per extraction worker (default: 1000)")
    parser.add_argument("--keep-parts", action="store_true",
                        help="Deprecated compatibility flag; source PDFs are no longer split")
    parser.add_argument("--hybrid", action="store_true",
                        help="Use the dual-engine extractor instead of lower-memory native-only")
    args = parser.parse_args()

    source = args.input_pdf.resolve()
    outdir = args.out.resolve()
    if not source.is_file() or source.suffix.lower() != ".pdf":
        parser.error(f"Input must be an existing PDF: {source}")
    if args.chunk_pages < 250 or args.chunk_pages > 1000:
        parser.error("--chunk-pages must be between 250 and 1000")
    if source == outdir or outdir in source.parents:
        parser.error("Output directory must not contain or overwrite the source PDF")

    outdir.mkdir(parents=True, exist_ok=True)
    work = outdir / ".chunk_work"
    part_root = work / "extracted_parts"
    part_root.mkdir(parents=True, exist_ok=True)
    # Older versions generated temporary split PDFs here; they are no longer
    # part of the pipeline and can safely be removed to reclaim disk space.
    shutil.rmtree(work / "pdf_parts", ignore_errors=True)
    manifest_path = work / "manifest.json"

    source_hash = sha256_file(source)
    # Keep PyMuPDF out of the long-lived coordinator; it is loaded only in this
    # short-lived page-count helper and in the bounded extraction subprocesses.
    count_result = subprocess.run(
        [sys.executable, "-c",
         "import fitz,sys; d=fitz.open(sys.argv[1]); print(len(d)); d.close()",
         str(source)],
        cwd=str(BASE), capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if count_result.returncode != 0:
        raise RuntimeError("Unable to count source PDF pages: " + (count_result.stderr or count_result.stdout)[-2000:])
    total_pages = int(count_result.stdout.strip().splitlines()[-1])
    if total_pages < 1:
        raise RuntimeError("Input PDF has no pages")
    source_name = args.source_name or source.name
    expected = {
        "source_name": source_name,
        "source_sha256": source_hash,
        "total_pages": total_pages,
        "chunk_pages": args.chunk_pages,
        "engine": "hybrid" if args.hybrid else "native_only",
        "chunked_extractor_sha256": sha256_file(Path(__file__).resolve()),
        "page_extractor_sha256": sha256_file(EXTRACTOR),
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hard_mismatches = [
            key for key in ("source_name", "source_sha256", "total_pages")
            if manifest.get(key) != expected[key]
        ]
        if hard_mismatches:
            raise RuntimeError(
                "Existing manifest belongs to a different source PDF or page count "
                f"({', '.join(hard_mismatches)}); use a fresh output directory to avoid mixing source data"
            )
        restart_keys = ("chunk_pages", "engine", "chunked_extractor_sha256", "page_extractor_sha256")
        changed_settings = [key for key in restart_keys if manifest.get(key) != expected[key]]
        if changed_settings:
            # Code/chunk-setting changes invalidate partial outputs. Keep the uploaded
            # source and any completed final artifacts until a complete replacement is
            # built, but discard only disposable per-chunk work and restart cleanly.
            print(
                "Checkpoint was produced by different extraction settings/code "
                f"({', '.join(changed_settings)}); restarting from the unchanged source PDF."
            )
            shutil.rmtree(part_root, ignore_errors=True)
            manifest = {**expected, "status": "RUNNING", "parts": []}
            atomic_json(manifest_path, manifest)
    else:
        manifest = {**expected, "status": "RUNNING", "parts": []}
        atomic_json(manifest_path, manifest)

    count = (total_pages + args.chunk_pages - 1) // args.chunk_pages
    prior = {int(p["index"]): p for p in manifest.get("parts", [])}
    parts: list[dict] = []
    # Lightweight live progress snapshots consumed by /admin/api/runtime.
    control_dir = Path(os.environ.get("CAPFIND_JOB_CONTROL_DIR", "")).expanduser()
    progress_path = control_dir / "progress.json" if str(control_dir) not in ("", ".") else None

    def write_progress(state: str, page: int, chunk_number: int, message: str = "") -> None:
        if progress_path is None:
            return
        atomic_json(progress_path, {
            "state": state, "page": max(0, min(total_pages, int(page))),
            "total": total_pages, "chunk_count": max(0, int(chunk_number)),
            "total_chunks": count, "chunk_pages": args.chunk_pages,
            "message": message,
        })

    write_progress("RUNNING", 0, 0, "Preparing extraction")

    for idx in range(count):
        start = idx * args.chunk_pages
        end = min(start + args.chunk_pages, total_pages)
        number = idx + 1
        stem = f"part_{number:04d}"
        chunk_out = part_root / stem
        chunk_out.mkdir(parents=True, exist_ok=True)
        expected_csv = chunk_out / f"{source.stem}_cutoffs.csv"
        expected_json = chunk_out / f"{source.stem}_cutoffs.json"
        expected_audit = chunk_out / f"{source.stem}_page_audit.json"
        saved = prior.get(number)

        if (saved and saved.get("status") == "COMPLETED"
                and expected_csv.is_file() and expected_json.is_file()
                and expected_audit.is_file()):
            part_info = saved
            print(f"[{number}/{count}] already complete; skipping pages {start+1}-{end}")
            parts.append(part_info)
            continue

        write_progress("RUNNING", start + 1, number - 1, f"Extracting pages {start+1}-{end}")
        print(f"[{number}/{count}] pages {start+1}-{end}: extracting directly from source PDF")

        env = os.environ.copy()
        env["CAPFIND_PAGE_OFFSET"] = str(start)
        env["CAPFIND_TOTAL_PAGES"] = str(total_pages)
        env["CAPFIND_CHUNK_INDEX"] = str(number)
        env["CAPFIND_TOTAL_CHUNKS"] = str(count)
        command = [
            sys.executable, str(EXTRACTOR), str(source), "--out", str(chunk_out),
            "--start-page", str(start + 1), "--end-page", str(end),
            "--source-name", source_name,
        ]
        if number > 1:
            previous_context = part_root / f"part_{number - 1:04d}" / "final_context.json"
            if previous_context.is_file():
                command.extend(["--initial-context", str(previous_context)])
        if not args.hybrid:
            command.append("--native-only")
        log_path = chunk_out / "extractor.log"
        result = None
        # A child extractor can fail transiently under tight shared-instance memory
        # pressure. Retry this range in isolation before failing the whole PDF. Keep
        # completed chunks and the manifest so a later job retry resumes at this range.
        for attempt in range(1, 4):
            if attempt > 1:
                for artifact in (expected_csv, expected_json, expected_audit):
                    artifact.unlink(missing_ok=True)
                print(f"Chunk {number}/{count} retry {attempt}/3 for pages {start+1}-{end}", file=sys.stderr)
            with log_path.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, cwd=str(BASE), env=env,
                                        stdout=log, stderr=subprocess.STDOUT, check=False)
            if result.returncode == 0:
                break
            if attempt < 3:
                import time
                time.sleep(attempt * 2)
        if result is None or result.returncode != 0:
            write_progress("FAILED", start + 1, number - 1, f"Chunk {number} failed on pages {start+1}-{end}")
            manifest["status"] = "FAILED"
            manifest["failed_part"] = number
            manifest["failed_page_range"] = [start + 1, end]
            manifest["parts"] = parts + [{
                "index": number, "start_page": start + 1, "end_page": end,
                "page_count": end - start, "status": "FAILED",
            }]
            atomic_json(manifest_path, manifest)
            tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
            print("\n".join(tail), file=sys.stderr)
            print(f"Chunk {number} pages {start+1}-{end} failed after 3 attempts; completed chunks are retained for resume.", file=sys.stderr)
            return (result.returncode if result else 1) or 1

        _, _, _, rows = validate_chunk_artifacts(
            chunk_out, source.stem, source_name, start + 1, end
        )
        part_info = {
            "index": number,
            "start_page": start + 1,
            "end_page": end,
            "page_count": end - start,
            "rows": rows,
            "status": "COMPLETED",
            "csv": str(expected_csv.relative_to(outdir)),
            "json": str(expected_json.relative_to(outdir)),
            "audit": str(expected_audit.relative_to(outdir)),
        }
        prior[number] = part_info
        parts.append(part_info)
        write_progress("RUNNING", end, number, f"Completed chunk {number} of {count}")
        manifest["parts"] = parts + [
            p for n, p in sorted(prior.items()) if n > number
            and p.get("status") == "COMPLETED"
        ]
        manifest["status"] = "RUNNING"
        atomic_json(manifest_path, manifest)
        print(f"    completed: {rows:,} rows")

    manifest["parts"] = sorted(parts, key=lambda p: p["index"])
    manifest["status"] = "COMBINING"
    atomic_json(manifest_path, manifest)
    result = combine_outputs(outdir, source, manifest["parts"], total_pages, source_hash)
    manifest["status"] = "COMPLETED"
    manifest["result"] = result
    atomic_json(manifest_path, manifest)
    write_progress("COMPLETED", total_pages, count, "All pages extracted and coverage verified")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
