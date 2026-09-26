import hashlib

import pytest

from backend.admin.pipeline import MAX_PDF_BYTES, identify, security_check


def test_identify_cutoff_and_seat_filenames():
    assert identify("BCA_2026_C1.pdf") == ("CUTOFFS", "BCA", 2026, "C1", 1.0)
    assert identify("MCA_26_C2_SM.pdf") == ("SEATS", "MCA", 2026, "C2", 1.0)


def test_identify_partial_filename_has_partial_confidence():
    assert identify("BCA_results.pdf") == ("CUTOFFS", "BCA", None, None, 1 / 3)


def test_security_check_accepts_pdf_and_returns_sha256(tmp_path):
    pdf = tmp_path / "sample.pdf"
    payload = b"%PDF-1.7\nminimal test content"
    pdf.write_bytes(payload)

    size, digest = security_check(pdf)

    assert size == len(payload)
    assert digest == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    ("filename", "payload", "message"),
    [
        ("sample.txt", b"%PDF-1.7", "extension"),
        ("sample.pdf", b"not a pdf", "valid PDF"),
    ],
)
def test_security_check_rejects_invalid_upload(tmp_path, filename, payload, message):
    path = tmp_path / filename
    path.write_bytes(payload)

    with pytest.raises(ValueError, match=message):
        security_check(path)


def test_security_check_rejects_oversized_pdf(tmp_path, monkeypatch):
    path = tmp_path / "large.pdf"
    path.write_bytes(b"%PDF-" + b"x" * 10)
    monkeypatch.setattr("backend.admin.pipeline.MAX_PDF_BYTES", 5)

    with pytest.raises(ValueError, match="PDF exceeds"):
        security_check(path)
