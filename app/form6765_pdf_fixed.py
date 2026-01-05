"""PDF renderer for Form 6765.

Approach:
1) Use the provided blank template PDF as a background.
2) Draw line values onto a transparent overlay (ReportLab).
3) Merge overlay onto the template (pypdf).

This produces an IRS-faithful looking output while keeping logic separated.

You MUST calibrate coordinates once per template revision.
The defaults here are a starting point for the provided sample form.
"""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Dict, Tuple, Any

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

try:
    from pypdf import PdfReader, PdfWriter
except Exception as e:
    raise ImportError("pypdf is required for PDF merging. Add `pypdf` to requirements.txt") from e

from form6765_models import Form6765Document


def _fmt_money(x: Any) -> str:
    try:
        d = Decimal(str(x))
    except Exception:
        return ""
    # Match typical IRS formatting: no commas by default; keep cents.
    return f"{d:.2f}"

def _draw_right(c, x: float, y: float, text: str, y_nudge: float = -2.0) -> None:
    if text is None:
        return
    s = str(text)
    if not s:
        return
    c.drawRightString(x, y + y_nudge, s)

def _draw_left(c, x: float, y: float, text: str, y_nudge: float = -2.0) -> None:
    if text is None:
        return
    s = str(text)
    if not s:
        return
    c.drawString(x, y + y_nudge, s)

def _mark(c, x: float, y: float, label: str) -> None:
    # small dot + label for coordinate calibration
    c.saveState()
    c.setFont("Helvetica", 6)
    c.circle(x, y, 2, stroke=1, fill=0)
    c.drawString(x + 3, y + 3, label)
    c.restoreState()



# ---- Coordinate maps ----
# Coordinates are (x, y) in points (1/72 inch) with origin at bottom-left.
# These are approximate placements for the sample PDF.
# Calibrate by printing a test PDF, adjusting numbers until aligned.


def default_coords_page1() -> Dict[str, Tuple[float, float]]:
    # Page 1 has lines 1-34 and header fields.
    return {
        "name_on_return": (72, 708),
        "identifying_number": (455, 708),

        # Section A right-side input boxes
        "line_1": (520, 655),
        "line_2": (520, 635),
        "line_3": (520, 615),
        "line_4": (520, 595),
        "line_5": (520, 570),
        "line_6": (520, 550),
        "line_7": (520, 530),
        "line_8": (520, 510),
        "line_9": (520, 490),
        "line_11": (520, 445),
        "line_12": (520, 425),
        "line_13": (520, 405),
        "line_14": (520, 385),
        "line_15": (520, 365),
        "line_16": (520, 345),
        "line_17": (520, 315),

        # Section B right-side input boxes
        "line_18": (520, 250),
        "line_19": (520, 232),
        "line_20": (520, 214),
        "line_21": (520, 196),
        "line_22": (520, 178),
        "line_23": (520, 160),
        "line_24": (520, 136),
        "line_25": (520, 118),
        "line_26": (520, 100),
        "line_27": (520, 82),
        "line_28": (520, 64),
        "line_29": (520, 46),
        # lines 30-34 extend below; sample page may truncate bottom margin
    }


def default_coords_page2() -> Dict[str, Tuple[float, float]]:
    # Page 2 has lines 35-44.
    return {
        "line_35": (520, 675),
        "line_36": (520, 655),
        "line_37": (520, 635),
        "line_38": (520, 615),
        "line_39": (520, 545),
        "line_40": (520, 525),

        "line_42": (520, 425),
        "line_43": (520, 385),
        "line_44": (520, 345),
    }


def render_form6765_pdf(
    *,
    template_pdf_path: str,
    output_pdf_path: str,
    doc: Form6765Document,
    coords_page1: Dict[str, Tuple[float, float]] | None = None,
    coords_page2: Dict[str, Tuple[float, float]] | None = None,
    font_name: str = "Helvetica",
    font_size: int = 9,
    y_nudge: float = -2.0,
    debug: bool = False,
) -> str:
    coords_page1 = coords_page1 or default_coords_page1()
    coords_page2 = coords_page2 or default_coords_page2()

    reader = PdfReader(template_pdf_path)
    writer = PdfWriter()

    # --- Page 1 overlay ---
    overlay1 = io.BytesIO()
    base1 = reader.pages[0]
    page_w1 = float(base1.cropbox.width)
    page_h1 = float(base1.cropbox.height)
    c1 = canvas.Canvas(overlay1, pagesize=(page_w1, page_h1))
    c1.setFont(font_name, font_size)

    if debug:
        for k, (x, y) in coords_page1.items():
            _mark(c1, x, y, k)

    _draw_left(c1, coords_page1["name_on_return"][0], coords_page1["name_on_return"][1], doc.header.name_on_return, y_nudge=y_nudge)
    _draw_left(c1, coords_page1["identifying_number"][0], coords_page1["identifying_number"][1], doc.header.identifying_number, y_nudge=y_nudge)

    # write common lines present on page 1
    l = doc.lines
    page1_fields = {
        "line_1": l.line_1,
        "line_2": l.line_2,
        "line_3": l.line_3,
        "line_4": l.line_4,
        "line_5": l.line_5,
        "line_6": l.line_6,
        "line_7": l.line_7,
        "line_8": l.line_8,
        "line_9": l.line_9,
        "line_11": l.line_11_avg_gross_receipts,
        "line_12": l.line_12,
        "line_13": l.line_13,
        "line_14": l.line_14,
        "line_15": l.line_15,
        "line_16": l.line_16,
        "line_17": l.line_17,
        "line_18": l.line_18,
        "line_19": l.line_19,
        "line_20": l.line_20,
        "line_21": l.line_21,
        "line_22": l.line_22,
        "line_23": l.line_23,
        "line_24": l.line_24,
        "line_25": l.line_25,
        "line_26": l.line_26,
        "line_27": l.line_27,
        "line_28": l.line_28,
        "line_29": l.line_29_prior_3_year_qre_total,
    }
    for key, val in page1_fields.items():
        if key in coords_page1:
            _draw_right(c1, coords_page1[key][0], coords_page1[key][1], _fmt_money(val), y_nudge=y_nudge)

    c1.showPage()
    c1.save()
    overlay1.seek(0)
    ov_reader1 = PdfReader(overlay1)

    base1.merge_page(ov_reader1.pages[0])
    writer.add_page(base1)

    # --- Page 2 overlay ---
    if len(reader.pages) > 1:
        overlay2 = io.BytesIO()
        base2 = reader.pages[1]
        page_w2 = float(base2.cropbox.width)
        page_h2 = float(base2.cropbox.height)
        c2 = canvas.Canvas(overlay2, pagesize=(page_w2, page_h2))
        c2.setFont(font_name, font_size)

        if debug:
            for k, (x, y) in coords_page2.items():
                _mark(c2, x, y, k)

        page2_fields = {
            "line_35": l.line_35,
            "line_36": l.line_36,
            "line_37": l.line_37,
            "line_38": l.line_38,
            "line_39": l.line_39,
            "line_40": l.line_40,
            "line_42": l.line_42,
            "line_43": l.line_43,
            "line_44": l.line_44,
        }
        for key, val in page2_fields.items():
            if key in coords_page2:
                _draw_right(c2, coords_page2[key][0], coords_page2[key][1], _fmt_money(val), y_nudge=y_nudge)

        c2.showPage()
        c2.save()
        overlay2.seek(0)
        ov_reader2 = PdfReader(overlay2)

        base2.merge_page(ov_reader2.pages[0])
        writer.add_page(base2)

    with open(output_pdf_path, "wb") as f:
        writer.write(f)
    return output_pdf_path
