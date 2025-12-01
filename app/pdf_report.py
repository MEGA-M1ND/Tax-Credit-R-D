# pdf_report.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
from typing import List, Dict


def generate_claim_pdf(out_path: str, company: str,
                       projects_summary: List[Dict],
                       traces: List[Dict]) -> str:
    c = canvas.Canvas(out_path, pagesize=A4)
    w, h = A4
    y = h - 50

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"R&D Credit Claim Summary — {company}")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Generated: {datetime.utcnow().isoformat()}Z")
    y -= 26

    # Projects section
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Projects")
    y -= 16
    c.setFont("Helvetica", 10)
    for p in projects_summary:
        line = f"- [{p['project_id']}] {p['project_name']} • eligible={p['eligible']} • conf={p['confidence']:.2f}"
        c.drawString(40, y, line[:110])
        y -= 14
        if y < 60:
            c.showPage()
            y = h - 50

    # Trace summary section
    c.showPage()
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, h - 50, "Trace Checksums (tamper evidence)")
    y = h - 70
    c.setFont("Helvetica", 9)
    for t in traces:
        head = f"{t.get('project_id','?')} • model={t.get('model_name','?')} • chk={t.get('checksum_sha256','')[:16]}…"
        c.drawString(40, y, head[:110]); y -= 12
        if y < 60:
            c.showPage()
            y = h - 50

    c.save()
    return out_path
