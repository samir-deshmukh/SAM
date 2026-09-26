import hashlib
import re
from pathlib import Path

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
        data_type, family, year, round_name, confidence = identify(
            original_filename or Path(path).name
        )
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
