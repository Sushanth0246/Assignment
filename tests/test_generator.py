"""Certificate generation (the PDF template itself)."""
from datetime import date

from app.generator import generate_certificate


def _generate(path, name="Asha Rao", **kw):
    return generate_certificate(
        recipient_name=name,
        certificate_title=kw.get("title", "Certificate of Completion"),
        course_name=kw.get("course", "Intro to Python"),
        issue_date=date(2026, 10, 7),
        certificate_id="abc123",
        output_path=path,
    )


def test_generates_a_valid_pdf_file(tmp_path):
    out = _generate(tmp_path / "nested" / "cert.pdf")
    assert out.exists()
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 500


def test_no_temp_file_left_behind(tmp_path):
    _generate(tmp_path / "cert.pdf")
    assert [p.name for p in tmp_path.iterdir()] == ["cert.pdf"]


def test_very_long_text_still_generates(tmp_path):
    out = _generate(tmp_path / "long.pdf", name="W" * 100, course="C" * 190, title="T" * 120)
    assert out.read_bytes().startswith(b"%PDF")


def test_certificate_contains_recipient_specific_info(tmp_path):
    # ReportLab compresses page streams by default; turn that off to inspect text.
    from reportlab import rl_config
    rl_config.pageCompression = 0
    try:
        out = _generate(tmp_path / "c.pdf", name="Zaphod Beeblebrox")
    finally:
        rl_config.pageCompression = 1
    data = out.read_bytes()
    assert b"Zaphod Beeblebrox" in data
    assert b"Intro to Python" in data
