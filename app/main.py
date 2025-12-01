from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd
import json, glob, time, uuid, os, logging
from io import BytesIO

from app.models import ProjectRecord, PipelineRequest
from app.reasoning import *
from app.trace_logger import ImmutableTraceLogger
from app.agentic_pipeline import build_graph

from app.contracts.form_6765 import CreditInputs, Form6765Document
from app.logic.credit_calc import compute_credit
from app.exports.evidence_pack import build_evidence_pack

from jinja2 import Template
from reportlab.lib.pagesizes import LETTER, A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

import io, csv

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="AI R&D Tax Credit Agent", version="0.4.0")
graph = build_graph()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

logger = ImmutableTraceLogger(base_dir="traces")
FORCE_LLM = os.getenv("FORCE_LLM", "false").lower() in ("1", "true", "yes")


def _pdf_bytes_from_lines(title: str, lines: List[str]) -> bytes:
    """
    Very small helper to create a lean, text-only PDF from a list of lines.
    This keeps the MVP self-contained without external system dependencies.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER
    y = height - 72
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, y, title)
    y -= 24
    c.setFont("Helvetica", 10)
    for ln in lines:
        # Naive wrapping at ~95 characters
        for sub in [ln[i:i+95] for i in range(0, len(ln), 95)]:
            if y < 72:
                c.showPage()
                y = height - 72
                c.setFont("Helvetica", 10)
            c.drawString(72, y, sub)
            y -= 14
    c.showPage()
    c.save()
    return buf.getvalue()


# -------------------------
# Health
# -------------------------
@app.get("/health")
def health():
    return {"status": "ok", "time": time.time(), "use_llm": USE_LLM, "model": MODEL_NAME}


# -------------------------
# Classify endpoint (supports mode + max_rows)
# -------------------------
import asyncio, hashlib

CONCURRENCY = int(os.getenv("LLM_CONCURRENCY", "5"))


@app.post("/classify_rnd")
async def classify_rnd(
    file: UploadFile = File(...),
    user_id: str = Form("demo-user"),
    mode: str = Form("hybrid"),
    max_rows: int = Form(50)
):
    log.info("HIT /classify_rnd by %s mode=%s max_rows=%s", user_id, mode, max_rows)
    if FORCE_LLM and not USE_LLM and mode != "rule":
        return {"results": [], "count": 0, "error": "LLM is required but OPENAI_API_KEY is not set."}

    df = pd.read_csv(file.file)
    df.columns = df.columns.str.lower()
    expected = {"project_id", "project_name", "description"}
    if not expected.issubset(df.columns):
        return {"results": [], "count": 0, "error": f"CSV must contain: {expected}"}
    if len(df) > max_rows:
        df = df.iloc[:max_rows].copy()

    # in-request cache keyed by description hash
    cache: dict[str, dict] = {}
    sem = asyncio.Semaphore(CONCURRENCY)

    def dhash(text: str) -> str:
        return hashlib.sha256((text or "").strip().lower().encode("utf-8")).hexdigest()

    async def process_row(row) -> dict:
        record = ProjectRecord(
            project_id=str(row.get("project_id")), project_name=str(row.get("project_name")),
            description=str(row.get("description")),
            department=str(row.get("department")) if "department" in df.columns else None,
            cost=float(row.get("cost")) if "cost" in df.columns and pd.notnull(row.get("cost")) else None,
            start_date=str(row.get("start_date")) if "start_date" in df.columns else None,
            end_date=str(row.get("end_date")) if "end_date" in df.columns else None,
        )

        key = dhash(record.description)

        # 1) hybrid pre-check with rule to avoid LLM
        if mode == "rule" or (mode == "hybrid" and not USE_LLM):
            rb_eligible, rb_conf, rb_rat = rule_based_classifier(record.description)
            classification = {
                "project_id": record.project_id, "project_name": record.project_name,
                "eligible": rb_eligible, "confidence": rb_conf, "rationale": rb_rat
            }
            trace = {
                "user_id": user_id, "project_id": record.project_id, "region": "US-IRS-Section-41",
                "model_name": "rule-based:v0", "reviewer_id": None, "legal_hold_flag": False,
                "steps": [{
                    "step_id": str(uuid.uuid4()), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "model_name": "rule-based:v0", "thought": "Rule engine quick pass.",
                    "action": "classify_rule",
                    "observation": f"eligible={rb_eligible}, confidence={rb_conf:.2f}",
                    "confidence": rb_conf
                }]
            }
        else:
            # mode is llm or hybrid w/ LLM escalation
            if mode == "hybrid":
                rb_eligible, rb_conf, rb_rat = rule_based_classifier(record.description)
                if rb_conf < 0.45 or rb_conf > 0.75:
                    # confident rule => skip LLM
                    classification = {
                        "project_id": record.project_id, "project_name": record.project_name,
                        "eligible": rb_eligible, "confidence": rb_conf,
                        "rationale": "Hybrid kept rule result → " + rb_rat
                    }
                    trace = {
                        "user_id": user_id, "project_id": record.project_id, "region": "US-IRS-Section-41",
                        "model_name": "rule-based:v0", "reviewer_id": None, "legal_hold_flag": False,
                        "steps": [{
                            "step_id": str(uuid.uuid4()), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "model_name": "rule-based:v0", "thought": "Hybrid skip LLM (confident rule).",
                            "action": "classify_rule",
                            "observation": f"eligible={rb_eligible}, confidence={rb_conf:.2f}",
                            "confidence": rb_conf
                        }]
                    }
                else:
                    # uncertain -> LLM (with cache)
                    if key in cache:
                        classification, trace = cache[key]["classification"], cache[key]["trace"]
                    else:
                        async with sem:
                            cls_obj, trace = await analyze_project_async(record, user_id=user_id)
                        classification = {
                            "project_id": cls_obj.project_id, "project_name": record.project_name,
                            "eligible": cls_obj.eligible, "confidence": cls_obj.confidence,
                            "rationale": cls_obj.rationale
                        }
                        cache[key] = {"classification": classification, "trace": trace}
            else:
                # pure llm (with cache)
                if key in cache:
                    classification, trace = cache[key]["classification"], cache[key]["trace"]
                else:
                    async with sem:
                        cls_obj, trace = await analyze_project_async(record, user_id=user_id)
                    classification = {
                        "project_id": cls_obj.project_id, "project_name": record.project_name,
                        "eligible": cls_obj.eligible, "confidence": cls_obj.confidence,
                        "rationale": cls_obj.rationale
                    }
                    cache[key] = {"classification": classification, "trace": trace}

        path = logger.write_trace(trace)
        return {
            **classification,
            "model_used": (
                "openai:" + MODEL_NAME
                if (USE_LLM and mode != "rule" and trace["model_name"] != "rule-based:v0")
                else "rule-based:v0"
            ),
            "trace_path": path
        }

    # fan out
    tasks = [process_row(row) for _, row in df.iterrows()]
    results = await asyncio.gather(*tasks)
    # Defensive: ensure results is a list of dicts; log and normalize any unexpected items
    normalized = []
    for i, r in enumerate(results):
        if not isinstance(r, dict):
            log.warning("classify_rnd: row %s returned non-dict result: %r", i, r)
            normalized.append({"project_id": None, "error": "processing_failed"})
            continue
        # Ensure minimal keys exist
        if "project_id" not in r:
            log.warning("classify_rnd: row %s missing project_id, adding placeholder", i)
            r.setdefault("project_id", None)
        normalized.append(r)

    return {"results": normalized, "count": len(normalized)}


# -------------------------
# PDF from CSV (same mode + max_rows behavior)
# -------------------------
@app.post("/report_pdf")
async def report_pdf(
    file: UploadFile = File(...),
    user_id: str = Form("demo-user"),
    mode: str = Form("hybrid"),
    max_rows: int = Form(50)
):
    log.info("HIT /report_pdf by %s mode=%s max_rows=%s", user_id, mode, max_rows)

    if FORCE_LLM and not USE_LLM and mode != "rule":
        return {"error": "LLM is required but OPENAI_API_KEY is not set."}

    try:
        df = pd.read_csv(file.file)
        df.columns = df.columns.str.lower()

        expected_cols = {"project_id", "project_name", "description"}
        if not expected_cols.issubset(set(df.columns)):
            return {"error": f"Input must include columns: {expected_cols}"}

        if len(df) > max_rows:
            df = df.iloc[:max_rows].copy()

        rows = []
        trace_paths = []
        eligible_count = 0

        for _, row in df.iterrows():
            record = ProjectRecord(
                project_id=str(row.get("project_id")),
                project_name=str(row.get("project_name")),
                description=str(row.get("description")),
                department=str(row.get("department")) if "department" in df.columns else None,
                cost=float(row.get("cost")) if "cost" in df.columns and pd.notnull(row.get("cost")) else None,
                start_date=str(row.get("start_date")) if "start_date" in df.columns else None,
                end_date=str(row.get("end_date")) if "end_date" in df.columns else None,
            )

            # mirror the classify path selection
            if mode == "rule" or (mode == "hybrid" and not USE_LLM):
                eligible, conf, rationale = rule_based_classifier(record.description)
                classification = {
                    "eligible": eligible, "confidence": conf, "rationale": rationale
                }
                trace = {
                    "user_id": user_id,
                    "project_id": record.project_id,
                    "steps": [{
                        "step_id": str(uuid.uuid4()),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "model_name": "rule-based:v0",
                        "thought": "Rule engine quick pass.",
                        "action": "classify_rule",
                        "observation": f"eligible={eligible}, confidence={conf:.2f}",
                        "confidence": conf
                    }],
                    "model_name": "rule-based:v0",
                    "region": "US-IRS-Section-41",
                    "reviewer_id": None,
                    "legal_hold_flag": False
                }
            else:
                if mode == "hybrid":
                    rb_eligible, rb_conf, rb_rat = rule_based_classifier(record.description)
                    if 0.45 <= rb_conf <= 0.75:
                        classification_obj, trace = analyze_project(record, user_id=user_id)
                        classification = {
                            "eligible": classification_obj.eligible,
                            "confidence": classification_obj.confidence,
                            "rationale": classification_obj.rationale
                        }
                    else:
                        classification = {
                            "eligible": rb_eligible,
                            "confidence": rb_conf,
                            "rationale": "Hybrid kept rule result → " + rb_rat
                        }
                        trace = {
                            "user_id": user_id,
                            "project_id": record.project_id,
                            "steps": [{
                                "step_id": str(uuid.uuid4()),
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "model_name": "rule-based:v0",
                                "thought": "Hybrid: LLM skipped due to confident rule result.",
                                "action": "classify_rule",
                                "observation": f"eligible={rb_eligible}, confidence={rb_conf:.2f}",
                                "confidence": rb_conf
                            }],
                            "model_name": "rule-based:v0",
                            "region": "US-IRS-Section-41",
                            "reviewer_id": None,
                            "legal_hold_flag": False
                        }
                else:
                    classification_obj, trace = analyze_project(record, user_id=user_id)
                    classification = {
                        "eligible": classification_obj.eligible,
                        "confidence": classification_obj.confidence,
                        "rationale": classification_obj.rationale
                    }

            path = logger.write_trace(trace)
            trace_paths.append(path)
            if classification["eligible"]:
                eligible_count += 1

            rows.append([
                record.project_id,
                record.project_name,
                "Yes" if classification["eligible"] else "No",
                f"{classification['confidence']:.2f}",
                (classification["rationale"][:120] + "...") if len(classification["rationale"]) > 120 else classification["rationale"]
            ])

        total = len(rows)
        ineligible_count = total - eligible_count

        # Build PDF
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("AI R&D Tax Credit — Audit Summary", styles["Title"]))
        story.append(Paragraph(f"User: {user_id}", styles["Normal"]))
        story.append(Paragraph(
            f"Mode: {mode}  |  Model: {'openai:'+MODEL_NAME if (USE_LLM and mode != 'rule') else 'rule-based:v0'}",
            styles["Normal"]
        ))
        story.append(Paragraph(
            f"Total: {total}  |  Eligible: {eligible_count}  |  Ineligible: {ineligible_count}",
            styles["Normal"]
        ))
        story.append(Spacer(1, 12))

        table_data = [["Project ID", "Project Name", "Eligible", "Confidence", "Rationale"]] + rows
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0e1117")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Trace Digest (per project)", styles["Heading2"]))
        for p in trace_paths:
            with open(p, "r", encoding="utf-8") as f:
                trace_json = json.load(f)
            steps = trace_json.get("steps", [])
            actions = ", ".join([s.get("action", "") for s in steps])
            model_used = trace_json.get("model_name", "")
            story.append(Paragraph(
                f"{trace_json.get('project_id')}: {actions}  |  model={model_used}",
                styles["Normal"]
            ))

        doc.build(story)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="rnd_audit_summary.pdf"'}
        )

    except ModuleNotFoundError:
        return {"error": "Report generation unavailable. Install: pip install reportlab"}
    except Exception as e:
        return {"error": f"PDF generation failed: {e}"}


@app.post("/agentic_pipeline")
async def agentic_pipeline(req: PipelineRequest):
    """
    Full agentic demo endpoint.
    Accepts a single project + list of expenses and runs:
    - EligibilityAgent
    - ExpenseAgent
    - NarrativeAgent
    - EvidenceAgent
    """
    initial_state = {
        "project": req.project.model_dump(),
        "raw_expenses": [e.model_dump() for e in req.expenses],
    }
    final_state = graph.invoke(initial_state)
    return final_state["summary"]


# -------------------------
# Credit computation (ASC vs Regular)
# -------------------------
@app.post("/compute_credit")
def compute_credit_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute federal R&D credit using a lean ASC vs Regular comparison.

    Example body:
    {
      "year": 2024,
      "qre_current": 117700,
      "qre_prior_3yrs": {"2023": 90000, "2022": 80000, "2021": 70000},
      "gross_receipts_prior_4yrs": {"2023": 400000, "2022": 380000, "2021": 360000, "2020": 340000},
      "elect_280c": true,
      "method": "ASC"
    }
    """
    ci = CreditInputs(**payload)
    co = compute_credit(ci)

    form = Form6765Document(
        tax_year=ci.year,
        method=co.method_selected,
        lines=co.line_map,
        explanations=co.explanations,
    )

    return {
        "inputs": ci.model_dump(),
        "credit": co.model_dump(),
        "form6765": form.model_dump(),
    }


# -------------------------
# Evidence Pack (ZIP)
# -------------------------
@app.post("/evidence_pack")
def evidence_pack_api(payload: Dict[str, Any]) -> Response:
    """
    Build a downloadable Evidence Pack (ZIP) containing:
      - narrative.md
      - form_6765.pdf (lean textual preview)
      - qre.csv
      - traces.json
      - manifest.json with SHA-256 hashes

    Example body:
    {
      "run_id": "string-uuid-or-name",
      "form_lines": ["Form 6765 (Demo Preview)", "A1: 117700", ...],
      "qre_rows": [
        ["Senior ML engineer salary", 54000, "WAGES", true, 54000],
        ...
      ],
      "narrative_md": "# Narrative\\n\\n...",
      "traces": {...}
    }
    """
    run_id = payload.get("run_id") or str(uuid.uuid4())
    narrative_md: str = payload.get("narrative_md") or "# Narrative\n\n(Empty)"
    traces: Dict[str, Any] = payload.get("traces") or {}
    qre_rows: List[List[Any]] = payload.get("qre_rows") or []

    # Build QRE CSV in memory
    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["description", "amount", "category", "eligible", "qre_amount"])
    for r in qre_rows:
        writer.writerow(r)
    qre_csv_bytes = csv_buf.getvalue().encode("utf-8")

    # Build a lean text PDF from line-like strings
    form_lines: List[str] = payload.get("form_lines") or [
        "Form 6765 (Demo Preview)",
        "— Lean MVP —",
    ]
    form_pdf_bytes = _pdf_bytes_from_lines("Form 6765 — Demo", form_lines)

    zip_bytes = build_evidence_pack(
        run_id=run_id,
        form_pdf=form_pdf_bytes,
        qre_csv=qre_csv_bytes,
        narrative_md=narrative_md,
        traces_json=traces,
    )

    headers = {
        "Content-Disposition": f'attachment; filename="{run_id}_evidence_pack.zip"'
    }
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)


# -------------------------
# Trace utilities
# -------------------------
@app.get("/traces/list")
def traces_list(limit: int = 50):
    files = sorted(glob.glob(os.path.join(logger.base_dir, "trace_*.json")), reverse=True)[:limit]
    return {"count": len(files), "items": [os.path.basename(f) for f in files]}


@app.get("/traces/read")
def traces_read(fname: str):
    path = os.path.join(logger.base_dir, os.path.basename(fname))
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.get("/trace_verify")
def trace_verify(path: str = Query(..., description="Absolute or relative path to a saved trace JSON")):
    return {"path": path, "verified": logger.verify(path)}


@app.post("/trace_freeze")
def trace_freeze(path: str = Form(...)):
    p = Path(path)
    if not p.exists():
        return {"path": path, "status": "not_found"}

    data = json.loads(p.read_text())
    if data.get("legal_hold_flag") is True:
        return {"path": path, "status": "already_frozen"}

    data["legal_hold_flag"] = True
    data.pop("checksum_sha256", None)
    frozen_name = p.stem + "_FROZEN" + p.suffix
    frozen_path = logger.write_trace(data, filename=frozen_name)
    return {"path": frozen_path, "status": "frozen_copy_created"}
