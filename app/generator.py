"""PDF certificate generation using ReportLab.

This module *is* the "predefined template": one fixed landscape-A4 layout, with
the recipient/course/date filled in. Replace the drawing code to change the design.
"""
import os
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = landscape(A4)
NAVY = colors.HexColor("#1f3a5f")
GOLD = colors.HexColor("#b8962e")


def _fit_font_size(text: str, font: str, max_size: float, max_width: float) -> float:
    """Shrink the font until the text fits inside max_width."""
    size = max_size
    while size > 10 and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def generate_certificate(
    *,
    recipient_name: str,
    certificate_title: str,
    course_name: str,
    issue_date: date,
    certificate_id: str,
    output_path: Path,
) -> Path:
    """Render one certificate PDF to output_path and return the path.

    The file is written to a temp name and renamed at the end, so a crash can
    never leave a half-written PDF that looks like a valid certificate.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp")

    c = canvas.Canvas(str(tmp_path), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"{certificate_title} - {recipient_name}")
    cx = PAGE_W / 2
    usable = PAGE_W - 160

    # Double border
    c.setStrokeColor(NAVY)
    c.setLineWidth(6)
    c.rect(25, 25, PAGE_W - 50, PAGE_H - 50)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.rect(38, 38, PAGE_W - 76, PAGE_H - 76)

    # Title
    c.setFillColor(NAVY)
    size = _fit_font_size(certificate_title, "Helvetica-Bold", 38, usable)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(cx, PAGE_H - 130, certificate_title)

    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(cx - 120, PAGE_H - 150, cx + 120, PAGE_H - 150)

    # Body
    c.setFillColor(colors.HexColor("#444444"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(cx, PAGE_H - 200, "This is to certify that")

    c.setFillColor(NAVY)
    size = _fit_font_size(recipient_name, "Helvetica-Bold", 36, usable)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(cx, PAGE_H - 255, recipient_name)

    c.setStrokeColor(colors.HexColor("#999999"))
    c.setLineWidth(0.8)
    c.line(cx - 200, PAGE_H - 265, cx + 200, PAGE_H - 265)

    c.setFillColor(colors.HexColor("#444444"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(cx, PAGE_H - 305, "has successfully completed")

    c.setFillColor(NAVY)
    size = _fit_font_size(course_name, "Helvetica-Bold", 26, usable)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(cx, PAGE_H - 345, course_name)

    # Footer
    c.setFillColor(colors.HexColor("#444444"))
    c.setFont("Helvetica", 13)
    c.drawCentredString(cx, 110, f"Issued on {issue_date.strftime('%d %B %Y')}")
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawCentredString(cx, 60, f"Certificate ID: {certificate_id}")

    c.showPage()
    c.save()
    os.replace(tmp_path, output_path)
    return output_path
