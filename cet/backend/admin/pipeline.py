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


# Families are matched using explicit degree/program phrases, not arbitrary
# substrings. Keep this list ordered from most specific to most general.
_FAMILY_PATTERNS = (
    ("MPHARM", re.compile(r"\b(?:M\s*\.?\s*PHARM(?:ACY)?|MASTER OF PHARMACY)\b")),
    ("MARCH", re.compile(r"\b(?:M\s*\.?\s*ARCH(?:ITECTURE)?|MASTER OF ARCHITECTURE)\b")),
    ("MPLAN", re.compile(r"\b(?:M\s*\.?\s*PLAN(?:NING)?|MASTER OF PLANNING)\b")),
    ("ME", re.compile(r"\bM\s*\.?\s*E\.?\b")),
    ("PHARMD", re.compile(r"\b(?:PHARM\s*\.?D|DOCTOR OF PHARMACY)\b")),
    ("BARCH", re.compile(r"\b(?:B\s*\.?\s*ARCH(?:ITECTURE)?|BACHELOR OF ARCHITECTURE|(?:FIVE YEAR FULL TIME )?DEGREE COURSE IN ARCHITECTURE)\b")),
    ("BPLAN", re.compile(r"\b(?:B\s*\.?\s*PLAN(?:NING)?|BACHELOR OF PLANNING)\b")),
    ("MHMCT", re.compile(r"\b(?:M\s*HMCT|MASTER OF HOTEL MANAGEMENT)\b")),
    ("HMCT", re.compile(r"\b(?:HMCT|HOTEL MANAGEMENT AND CATERING TECHNOLOGY)\b")),
    ("BPHARM", re.compile(r"\b(?:B\s*\.?\s*PHARM(?:ACY)?|BACHELOR OF PHARMACY)\b")),
    ("MTECH", re.compile(r"\b(?:M\s*\.?\s*TECH|MASTER OF TECHNOLOGY)\b")),
    ("MPED", re.compile(r"\b(?:M\s*\.?\s*PED|MASTER OF PHYSICAL EDUCATION)\b")),
    ("BPED", re.compile(r"\b(?:B\s*\.?\s*PED|BACHELOR OF PHYSICAL EDUCATION)\b")),
    ("BDES", re.compile(r"\b(?:B\s*\.?\s*DES|BACHELOR OF DESIGN)\b")),
    ("LLB5", re.compile(r"\b(?:5\s*YEAR(?:S)?\s+LAW|FIVE YEAR LAW|BA\s*LLB|BBA\s*LLB|BCOM\s*LLB)\b")),
    ("LLB3", re.compile(r"\b(?:3\s*YEAR(?:S)?\s+LAW|THREE YEAR LAW|LLB)\b")),
    ("MED", re.compile(r"\b(?:M\s*\.?\s*ED|MASTER OF EDUCATION)\b")),
    ("BED", re.compile(r"\b(?:B\s*\.?\s*ED|BACHELOR OF EDUCATION)\b")),
    ("MCA", re.compile(r"\bMCA\b")),
    ("MBA", re.compile(r"\b(?:MBA|MMS|MASTER OF BUSINESS ADMINISTRATION)\b")),
    ("BCA", re.compile(r"\b(?:BCA|BACHELOR OF COMPUTER APPLICATIONS?)\b")),
    ("BBA", re.compile(r"\b(?:BBA|BMS|BBM|BACHELOR OF BUSINESS ADMINISTRATION|BACHELOR OF MANAGEMENT STUDIES)\b")),
    ("MTECH", re.compile(r"\bMASTER OF ENGINEERING\b")),
    ("BE", re.compile(r"\b(?:B\s*\.?\s*E\.?|B\s*\.?\s*TECH|BACHELOR OF ENGINEERING|BACHELOR OF TECHNOLOGY|ENGINEERING AND TECHNOLOGY|ENGINEERING CAP)\b")),
)


_FAMILY_STRONG_MARKERS = {
    "MPHARM": ("MASTER OF PHARMACY",),
    "MARCH": ("MASTER OF ARCHITECTURE",),
    "MPLAN": ("MASTER OF PLANNING",),
    "PHARMD": ("DOCTOR OF PHARMACY",),
    "BARCH": ("BACHELOR OF ARCHITECTURE",),
    "BPLAN": ("BACHELOR OF PLANNING",),
    "MHMCT": ("MASTER OF HOTEL MANAGEMENT",),
    "HMCT": ("HOTEL MANAGEMENT AND CATERING TECHNOLOGY",),
    "BPHARM": ("BACHELOR OF PHARMACY",),
    "MTECH": ("MASTER OF TECHNOLOGY", "MASTER OF ENGINEERING"),
    "MPED": ("MASTER OF PHYSICAL EDUCATION",),
    "BPED": ("BACHELOR OF PHYSICAL EDUCATION",),
    "BDES": ("BACHELOR OF DESIGN",),
    "LLB5": ("FIVE YEAR LAW", "BA LLB", "BBA LLB", "BCOM LLB"),
    "LLB3": ("THREE YEAR LAW",),
    "MED": ("MASTER OF EDUCATION",),
    "BED": ("BACHELOR OF EDUCATION",),
    "MCA": ("MASTER OF COMPUTER APPLICATIONS",),
    "MBA": ("MASTER OF BUSINESS ADMINISTRATION",),
    "BCA": ("BACHELOR OF COMPUTER APPLICATIONS", "BACHELOR OF COMPUTER APPLICATION"),
    "BBA": ("BACHELOR OF BUSINESS ADMINISTRATION", "BACHELOR OF MANAGEMENT STUDIES"),
    "BE": ("BACHELOR OF ENGINEERING", "BACHELOR OF TECHNOLOGY", "ENGINEERING AND TECHNOLOGY"),
}


def detect_course_family(value):
    """Identify a known CET program; return None when clues are missing or tied.

    Full degree titles outweigh incidental acronyms. If multiple families have
    equally strong evidence, return None so preflight stops instead of guessing.
    """
    text = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", str(value or "").upper())).strip()

    # Official CAP PDFs often mention the institution's engineering college in
    # every row. Do not let that incidental wording override the degree named
    # in the document heading.
    # Some official CAP lists combine closely related programs in one PDF.
    # Select the primary course named in the heading, rather than letting
    # program names repeated in individual college rows override the heading.
    # One 2026 CAP Round-IV MBA PDF has a known contradictory heading:
    # "Master of Computer Applications (MBA)" while its college rows say M.B.A.
    # In this specific case, the explicit MBA acronym and row program win.
    if "MASTER OF COMPUTER APPLICATIONS (MBA)" in text and re.search(r"\bM\.?\s*B\.?\s*A\.?\b", text):
        return "MBA"
    if "M.PHARM" in text and "PHARM.D" in text and "POST BACCALAUREATE" in text:
        return "MPHARM"
    if "B.PHARMACY" in text and "PHARM.D" in text and "POST GRADUATE" in text:
        return "BPHARM"
    if "MASTER OF ARCHITECTURE" in text or "POST GRADUATE COURSE IN ARCHITECTURE" in text:
        return "MARCH"
    if "MASTER OF PHARMACY" in text or "POST GRADUATE DEGREE COURSE IN PHARMACY" in text:
        return "MPHARM"
    if "DEGREE COURSE IN ARCHITECTURE" in text or "BACHELOR OF ARCHITECTURE" in text:
        return "BARCH"
    if "DEGREE COURSE IN PHARMACY" in text and "POST GRADUATE" not in text:
        return "BPHARM"
    if (
        "POST GRADUATE DEGREE COURSE IN ENGINEERING" in text
        or "POST GRADUATE TECHNICAL COURSES IN ENGINEERING" in text
    ):
        return "ME"

    scores = {}
    for family, pattern in _FAMILY_PATTERNS:
        hits = len(list(pattern.finditer(text)))
        if hits:
            scores[family] = hits
    for family, markers in _FAMILY_STRONG_MARKERS.items():
        bonus = sum(3 for marker in markers if marker in text)
        if bonus:
            scores[family] = scores.get(family, 0) + bonus
    if not scores:
        return None
    highest = max(scores.values())
    winners = [family for family, score in scores.items() if score == highest]
    return winners[0] if len(winners) == 1 else None


def extract_pdf_metadata(path, filename):
    """Recover year/round/family from the filename and PDF's first pages."""
    text = _pdf_text_probe(path).upper()
    upper_name = str(filename or "").upper()
    family = detect_course_family(text) or detect_course_family(upper_name)
    year = None
    year_match = re.search(r"(?:ACADEMIC YEAR|A\.Y\.)\s*[:\-]?\s*(20\d{2})\s*[-/]\s*\d{2}", text)
    if not year_match:
        year_match = re.search(r"\b(20\d{2})\s*[-/]\s*(?:20)?\d{2}\b", text)
    if year_match:
        year = int(year_match.group(1))
    round_name = None
    round_match = re.search(r"CAP\s*ROUND\s*[- ]?\s*(IV|III|II|I|[1-4])\b", text)
    if round_match:
        value = round_match.group(1)
        round_name = {"I":"C1","II":"C2","III":"C3","IV":"C4"}.get(value, f"C{value}")
    return family, year, round_name


def identify(filename):
    """Infer metadata from the filename without substring-based family guesses."""
    upper_name = str(filename or "").upper()
    data_type = "SEATS" if ("_SM" in upper_name or "SEAT" in upper_name or "MATRIX" in upper_name) else "CUTOFFS"
    family = detect_course_family(upper_name)
    year_match = re.search(r"(?:^|[_\-. ])(20\d{2}|\d{2})(?=[_\-. ]|$)", upper_name)
    year = int(year_match.group(1)) if year_match else None
    if year is not None and year < 100:
        year += 2000
    round_match = re.search(r"(?<![A-Z0-9])C([1-4])(?![A-Z0-9])", upper_name)
    round_name = f"C{round_match.group(1)}" if round_match else None
    fields = sum(value is not None for value in (family, year, round_name))
    confidence = fields / 3
    return data_type, family, year, round_name, confidence


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
        # The document's own title/heading outranks a misleading filename.
        family = pdf_family or family
        if not family:
            raise ValueError(
                "Could not confidently identify the course family from the PDF or filename. "
                "Import stopped rather than guessing a course; rename the PDF with its course name or check the source document."
            )
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
