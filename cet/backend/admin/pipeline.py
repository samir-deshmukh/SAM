import hashlib
import re
from pathlib import Path


def _pdf_text_probe(path, max_pages=8):
    """Read a small native-text sample for content-based PDF classification."""
    try:
        import pdfplumber
        chunks=[]
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:max_pages]:
                chunks.append(page.extract_text() or "")
        return "\n".join(chunks)
    except Exception:
        return ""


def extract_pdf_metadata(path, filename):
    """Recover year/round/family when a PDF filename omits them."""
    text = _pdf_text_probe(path).upper()
    upper_name = str(filename or "").upper()
    family = next(
        (value for value in ("BCA", "BBA", "MBA", "MCA") if value in upper_name),
        None,
    )
    if not family:
        family = next(
            (value for value in ("BCA", "BBA", "MBA", "MCA") if value in text),
            None,
        )
    year = None
    year_match = re.search(r"(?:ACADEMIC YEAR|A\.Y\.)\s*[:\-]?\s*(20\d{2})\s*[-/]\s*\d{2}", text)
    if not year_match:
        # Some CET seat-matrix PDFs print only the session, without the
        # literal "Academic Year" label. This is still deterministic
        # because the year pair is read from the PDF itself.
        year_match = re.search(r"\b(20\d{2})\s*[-/]\s*(?:20)?\d{2}\b", text)
    if year_match:
        year = int(year_match.group(1))
    round_name = None
    round_match = re.search(r"CAP\s*ROUND\s*[- ]?\s*(I{1,3}|IV|[1-4])\b", text)
    if round_match:
        value = round_match.group(1)
        round_name = {"I":"C1","II":"C2","III":"C3","IV":"C4"}.get(value, f"C{value}")
    return family, year, round_name


def detect_data_type(path, filename):
    """Identify seat matrices from PDF content as well as filename hints.

    Seat-matrix PDFs are frequently named generically (for example
    ``BCA 26 C1.pdf``), so filename-only detection can send them through the
    cutoff extractor. Content markers are stronger evidence when available.
    """
    name = str(filename or Path(path).name).upper()
    text = _pdf_text_probe(path).upper()
    seat_markers = (
        "SEAT DISTRIBUTION", "SEAT MATRIX", "CHOICE CODE", "CAP SEATS",
        "COURSE NAME", "PROVISIONAL SEAT DISTRIBUTION", "FINAL SEAT DISTRIBUTION",
        "NUMBER OF SEATS", "CATEGORY-WISE SEAT DISTRIBUTION",
    )
    cutoff_markers = ("PERCENTILE", "RANK", "GOPENH", "LOPENH", "STAGE-I")
    seat_score = sum(marker in text for marker in seat_markers)
    cutoff_score = sum(marker in text for marker in cutoff_markers)
    if seat_score >= 2 and seat_score > cutoff_score:
        return "SEATS"
    if re.search(r"(^|[ _.-])SM([ _.-]|$)", name) or "SEAT" in name or "MATRIX" in name:
        return "SEATS"
    return "CUTOFFS"

from .db import event, update_status
from .state import JobStatus

MAX_PDF_BYTES = 50 * 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def security_check(path):
    pdf_path = Path(path)
    size = pdf_path.stat().st_size

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("File extension must be .pdf")
    if size > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds 50 MiB limit")

    with open(pdf_path, "rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("File is not a valid PDF container")

    return size, sha256_file(pdf_path)


def identify(filename):
    upper_name = filename.upper()
    data_type = "SEATS" if ("_SM" in upper_name or "SEAT" in upper_name) else "CUTOFFS"
    family = next(
        (value for value in ("BCA", "BBA", "MBA", "MCA") if value in upper_name),
        None,
    )

    year_match = re.search(
        r"(?:^|[_\-. ])(20\d{2}|\d{2})(?=[_\-. ]|$)", upper_name
    )
    year = int(year_match.group(1)) if year_match else None
    if year is not None and year < 100:
        year += 2000

    round_match = re.search(r"(?<![A-Z0-9])(C\d)(?![A-Z0-9])", upper_name)
    round_name = round_match.group(1) if round_match else None

    fields = sum(value is not None for value in (family, year, round_name))
    confidence = fields / 3
    return data_type, family, year, round_name, confidence


def run_preflight(connection, job_id, path, original_filename=None):
    try:
        update_status(
            connection,
            job_id,
            JobStatus.SECURITY_CHECK.value,
            "Checking uploaded PDF",
        )
        event(
            connection,
            job_id,
            "SECURITY",
            "Valid PDF container and size check started",
            10,
        )

        size, sha256 = security_check(path)
        connection.execute(
            "UPDATE import_jobs SET sha256=?,size_bytes=? WHERE id=?",
            (sha256, size, job_id),
        )
        event(
            connection,
            job_id,
            "SECURITY",
            "SHA-256 fingerprint recorded",
            20,
        )

        update_status(
            connection,
            job_id,
            JobStatus.IDENTIFIED.value,
            "Identifying source metadata",
        )
        original = original_filename or Path(path).name
        data_type, family, year, round_name, confidence = identify(original)
        # Override filename-only type when the PDF itself clearly identifies
        # a seat matrix. This handles real uploads whose filenames are simply
        # ``BCA 26 C1.pdf`` or similar.
        data_type = detect_data_type(path, original)
        pdf_family, pdf_year, pdf_round = extract_pdf_metadata(path, original)
        family = family or pdf_family
        year = year or pdf_year
        round_name = round_name or pdf_round
        required_metadata = (family, year) if data_type == "SEATS" else (family, year, round_name)
        confidence = sum(value is not None for value in required_metadata) / len(required_metadata)
        connection.execute(
            "UPDATE import_jobs SET data_type=?,course_family=?,year=?,round=?,confidence=? WHERE id=?",
            (data_type, family, year, round_name, confidence, job_id),
        )
        event(
            connection,
            job_id,
            "IDENTIFICATION",
            f'Identified {data_type} / {family or "unknown family"} / '
            f'{year or "unknown year"} / {round_name or "unknown round"}',
            40,
        )

        update_status(
            connection,
            job_id,
            JobStatus.IDENTIFIED.value,
            "Preflight complete; processing will start automatically",
        )
        event(
            connection,
            job_id,
            "IDENTIFIED",
            "Preflight passed; automatic processing queued",
            40,
        )
        connection.commit()
        return True
    except Exception as exc:
        connection.execute(
            "UPDATE import_jobs SET status=?,error_message=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (JobStatus.FAILED.value, str(exc), job_id),
        )
        event(connection, job_id, "ERROR", str(exc), None)
        connection.commit()
        return False
