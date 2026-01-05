from dotenv import load_dotenv

# Load environment variables from .env file FIRST, before any other imports
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from typing import Dict, Any, List, Optional
import pandas as pd
from io import BytesIO
import json
import zipfile
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import BaseModel, Field

from .models import ProjectRecord
from .reasoning import analyze_project, analyze_project_async
from .trace import ImmutableTraceLogger
from .trace_logger import ImmutableTraceLogger as ImmutableTraceLoggerV2
from .auth import enforce_api_key
from .review_api import setup_review_routes
from .review_models import ReviewStatus
from .storage import get_storage
from .form6765_models import Form6765Header, Form6765Inputs
from .form6765_calc import compute_form6765, EligibilitySnapshot
from .form6765_pdf import render_form6765_pdf
from .form_lock_store import (
    create_eligibility_snapshot,
    get_active_form_lock,
    lock_form_version,
    save_form_version,
    get_form_version,
    get_snapshot,
    list_approved_projects,
    init_db as init_form_lock_db,
    DB_PATH as FORM_LOCK_DB_PATH,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5")
USE_LLM = bool(OPENAI_API_KEY)

FORM_TEMPLATE_DEFAULT = Path(__file__).resolve().parents[1] / "Sample_Form_6765_Template.pdf"
FORM_EXPORT_DIR = Path(__file__).resolve().parent / "exports" / "form6765"
FORM_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Ensure form lock database is initialized for downstream operations
init_form_lock_db(FORM_LOCK_DB_PATH)

app = FastAPI(title="AI R&D Tax Credit Agent - MVP API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = ImmutableTraceLogger()
logger_v2 = ImmutableTraceLoggerV2()  # For review traces
classification_cache: Dict[str, Dict[str, Any]] = {}
executor = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# Form 6765 request/response models
# ---------------------------------------------------------------------------


class Form6765GenerateRequest(BaseModel):
    header: Form6765Header
    inputs: Form6765Inputs
    project_ids: List[str] = Field(..., min_length=1)
    ruleset_version: str = Field(..., min_length=1)
    created_by: str = Field(..., min_length=1)
    reviewer_rollup: Dict[str, Any] = Field(default_factory=dict)
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    template_pdf_path: Optional[str] = None
    override_reason: Optional[str] = None
    lock_reason: Optional[str] = None
    save_pdf: bool = True


class Form6765GenerateResponse(BaseModel):
    form_version: Dict[str, Any]
    snapshot: Dict[str, Any]
    lock: Dict[str, Any]
    pdf_path: Optional[str] = None
    override_applied: bool = False


# Setup review routes
setup_review_routes(app)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/classify_rnd")
async def classify_rnd(
    file: UploadFile = File(...),
    user_id: str = Form("demo-user"),
    api_key: str = Depends(enforce_api_key),
) -> Dict[str, Any]:
    """
    Accept a CSV of projects and return classifications + write traces.
    Requires a valid API key.
    
    Enhanced response now includes:
    - recommended_status (RECOMMENDED_ELIGIBLE, RECOMMENDED_NOT_ELIGIBLE, or MANUAL_REVIEW)
    - confidence and reasoning from AI
    - trace_path for audit trail
    
    Does NOT overwrite human approvals/rejections - respects prior review decisions.
    """
    df = pd.read_csv(file.file)
    expected_cols = {"project_id", "project_name", "description"}
    if not expected_cols.issubset(set(df.columns)):
        return {"error": f"CSV must contain columns: {expected_cols}"}

    results = []
    loop = asyncio.get_event_loop()
    storage = get_storage()
    
    for _, row in df.iterrows():
        project_id = str(row.get("project_id"))
        record = ProjectRecord(
            project_id=project_id,
            project_name=str(row.get("project_name")),
            description=str(row.get("description")),
            department=str(row.get("department")) if "department" in df.columns else None,
            cost=float(row.get("cost")) if "cost" in df.columns and pd.notnull(row.get("cost")) else None,
            start_date=str(row.get("start_date")) if "start_date" in df.columns else None,
            end_date=str(row.get("end_date")) if "end_date" in df.columns else None,
        )
        # Run sync analyze_project in thread pool to avoid blocking event loop
        classification, trace = await loop.run_in_executor(
            executor,
            analyze_project,
            record,
            user_id
        )
        path = logger.write_trace(trace)

        # Step 4: Map AI output to recommendation status
        if classification.confidence < 0.5:
            recommended_status = ReviewStatus.MANUAL_REVIEW
        elif classification.eligible:
            recommended_status = ReviewStatus.RECOMMENDED_ELIGIBLE
        else:
            recommended_status = ReviewStatus.RECOMMENDED_NOT_ELIGIBLE
        
        # Step 9: Check if there's an approved/rejected outcome to respect
        current_review_state = storage.get_current_review_state(project_id)
        final_status = recommended_status
        if current_review_state.last_review:
            if current_review_state.last_review.status in (
                ReviewStatus.APPROVED,
                ReviewStatus.REJECTED,
                ReviewStatus.OVERRIDDEN,
            ):
                # Human decision exists, don't override it
                final_status = current_review_state.last_review.status

        payload = {
            "project_id": classification.project_id,
            "project_name": record.project_name,
            "eligible": classification.eligible,
            "confidence": classification.confidence,
            "rationale": classification.rationale,
            "region": classification.region,
            "trace_path": path,
            "recommended_status": recommended_status.value,
            "final_status": final_status.value,
        }
        results.append(payload)
        classification_cache[classification.project_id] = payload

    return {"count": len(results), "results": results}


def _get_project_data(project_id: str) -> Dict[str, Any]:
    """
    Lookup project classification + trace metadata.
    MVP: in-memory cache populated by /classify_rnd.
    """
    if project_id not in classification_cache:
        raise ValueError(f"project_id {project_id} not found in cache. Run /classify_rnd first.")
    return classification_cache[project_id]


@app.post("/form6765/generate", response_model=Form6765GenerateResponse)
async def generate_form6765(
    payload: Form6765GenerateRequest,
    api_key: str = Depends(enforce_api_key),
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
) -> Form6765GenerateResponse:
    """Freeze approved projects, compute Form 6765, persist, lock, and optionally render PDF."""

    project_ids = [pid.strip() for pid in payload.project_ids if pid.strip()]
    if not project_ids:
        raise HTTPException(status_code=400, detail="project_ids must include at least one identifier")

    tax_year = payload.header.tax_year

    existing_lock = get_active_form_lock(FORM_LOCK_DB_PATH, tax_year)
    override_applied = False
    lock_reason = payload.lock_reason or f"Initial form lock for tax year {tax_year}"
    role_normalized = x_role.strip().upper() if x_role else None
    allowed_override_roles = {"ADMIN", "PARTNER", "DIRECTOR"}
    override_requested = bool(payload.override_reason and payload.override_reason.strip())
    override_reason_clean = payload.override_reason.strip() if override_requested else None

    if override_requested:
        if not role_normalized:
            raise HTTPException(status_code=403, detail="Override requires X-Role header")
        if role_normalized not in allowed_override_roles:
            raise HTTPException(
                status_code=403,
                detail="Override requires X-Role header of admin, partner, or director.",
            )
        if len(override_reason_clean) < 30:
            raise HTTPException(
                status_code=400,
                detail="override_reason must be at least 30 characters when provided.",
            )

    if existing_lock:
        if not override_requested:
            raise HTTPException(
                status_code=409,
                detail="Active form lock exists; provide override_reason with at least 30 characters to regenerate.",
            )
        override_applied = True
        lock_reason = override_reason_clean

    approved_projects = list_approved_projects(FORM_LOCK_DB_PATH, project_ids)
    if not approved_projects:
        if override_requested and role_normalized in allowed_override_roles:
            override_applied = True
            approved_projects = project_ids
            lock_reason = override_reason_clean or lock_reason
        else:
            raise HTTPException(
                status_code=400,
                detail="No approved projects available to include in snapshot. Complete review approvals or supply override credentials.",
            )

    snapshot_id, snapshot_sha, approved_projects = create_eligibility_snapshot(
        db_path=FORM_LOCK_DB_PATH,
        tax_year=tax_year,
        project_ids=project_ids,
        created_by=payload.created_by,
        approved_project_ids=approved_projects,
    )

    snapshot_model = EligibilitySnapshot(
        snapshot_id=snapshot_id,
        approved_project_ids=approved_projects,
        snapshot_sha256=snapshot_sha,
    )

    try:
        document = compute_form6765(
            header=payload.header,
            inputs=payload.inputs,
            snapshot=snapshot_model,
            ruleset_version=payload.ruleset_version,
            prompt_version=payload.prompt_version,
            model_name=payload.model_name,
            reviewer_rollup=payload.reviewer_rollup,
        )
    except ValueError as exc:  # validation error from compute_form6765
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pdf_path: Optional[str] = None
    if payload.save_pdf:
        template_path = Path(payload.template_pdf_path) if payload.template_pdf_path else FORM_TEMPLATE_DEFAULT
        if not template_path.exists():
            raise HTTPException(status_code=404, detail=f"Template PDF not found: {template_path}")
        output_path = FORM_EXPORT_DIR / f"{document.form_version_id}.pdf"
        pdf_path = render_form6765_pdf(
            template_pdf_path=str(template_path),
            output_pdf_path=str(output_path),
            doc=document,
        )

    save_form_version(
        db_path=FORM_LOCK_DB_PATH,
        tax_year=tax_year,
        snapshot_id=snapshot_id,
        form_version_id=document.form_version_id,
        form_sha256=document.form_version_sha256,
        form_json=document.model_dump(mode="json"),
        created_by=payload.created_by,
        pdf_path=str(pdf_path) if pdf_path else None,
    )

    lock_id = lock_form_version(
        db_path=FORM_LOCK_DB_PATH,
        tax_year=tax_year,
        form_version_id=document.form_version_id,
        locked_by=payload.created_by,
        lock_reason=lock_reason,
    )

    form_record = get_form_version(FORM_LOCK_DB_PATH, document.form_version_id)
    snapshot_record = get_snapshot(FORM_LOCK_DB_PATH, snapshot_id)
    lock_record = get_active_form_lock(FORM_LOCK_DB_PATH, tax_year)

    return Form6765GenerateResponse(
        form_version=form_record or {
            "form_version_id": document.form_version_id,
            "tax_year": tax_year,
            "snapshot_id": snapshot_id,
            "form_sha256": document.form_version_sha256,
            "form_json": document.model_dump(mode="json"),
            "pdf_path": pdf_path,
            "created_at_utc": None,
            "created_by": payload.created_by,
        },
        snapshot=snapshot_record or {
            "snapshot_id": snapshot_id,
            "tax_year": tax_year,
            "snapshot_sha256": snapshot_sha,
            "approved_project_ids": approved_projects,
            "created_at_utc": None,
            "created_by": payload.created_by,
        },
        lock=lock_record or {
            "lock_id": lock_id,
            "active_form_version_id": document.form_version_id,
            "locked_at_utc": None,
            "locked_by": payload.created_by,
            "lock_reason": lock_reason,
            "is_active": True,
        },
        pdf_path=str(pdf_path) if pdf_path else None,
        override_applied=override_applied,
    )


@app.get("/form6765/{tax_year}/active", response_model=Form6765GenerateResponse)
async def get_active_form6765(
    tax_year: int,
    api_key: str = Depends(enforce_api_key),
) -> Form6765GenerateResponse:
    """Return the currently locked Form 6765 package for a tax year."""

    lock_record = get_active_form_lock(FORM_LOCK_DB_PATH, tax_year)
    if not lock_record:
        raise HTTPException(status_code=404, detail=f"No active form lock for tax year {tax_year}")

    form_record = get_form_version(FORM_LOCK_DB_PATH, lock_record["active_form_version_id"])
    if not form_record:
        raise HTTPException(status_code=404, detail="Form version referenced by lock not found")

    snapshot_record = get_snapshot(FORM_LOCK_DB_PATH, form_record["snapshot_id"])
    pdf_path = form_record.get("pdf_path") if isinstance(form_record, dict) else None

    return Form6765GenerateResponse(
        form_version=form_record,
        snapshot=snapshot_record or {},
        lock=lock_record,
        pdf_path=pdf_path,
        override_applied=False,
    )


@app.get("/form6765/form/{form_version_id}/pdf")
async def download_form6765_pdf(
    form_version_id: str,
    api_key: str = Depends(enforce_api_key),
):
    """Stream the stored PDF for a specific form version."""

    form_record = get_form_version(FORM_LOCK_DB_PATH, form_version_id)
    if not form_record:
        raise HTTPException(status_code=404, detail=f"Form version {form_version_id} not found")

    pdf_path = form_record.get("pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="No PDF stored for this form version")

    path_obj = Path(pdf_path)
    if not path_obj.exists():
        raise HTTPException(status_code=404, detail="Stored PDF path is missing")

    return FileResponse(path=path_obj, filename=path_obj.name, media_type="application/pdf")


@app.post("/audit_package")
async def audit_package(
    project_id: str = Form(...),
    api_key: str = Depends(enforce_api_key),
):
    """
    Return a ZIP with:
    - classification_summary.json (project + eligibility + rationale)
    - trace_pointer.txt (path to the encrypted trace file)
    """
    try:
        data = _get_project_data(project_id)
    except ValueError as e:
        return {"error": str(e)}

    try:
        storage = get_storage()
        review_state = storage.get_current_review_state(project_id)
        
        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("classification_summary.json", json.dumps(data, indent=2))
            zf.writestr("trace_pointer.txt", data.get("trace_path", ""))
            
            # Include review history if it exists
            if review_state.history:
                review_history = {
                    "project_id": project_id,
                    "current_status": review_state.current_status.value,
                    "history": [
                        {
                            "review_id": r.review_id,
                            "status": r.status.value,
                            "reviewer_name": r.reviewer_name,
                            "reviewer_role": r.reviewer_role.value,
                            "reason": r.reason,
                            "timestamp": r.timestamp.isoformat(),
                            "trace_path": r.review_trace_path,
                        }
                        for r in review_state.history
                    ]
                }
                zf.writestr("review_history.json", json.dumps(review_history, indent=2))

        zip_buf.seek(0)
        headers = {
            "Content-Disposition": f'attachment; filename="audit_package_{project_id}.zip"',
            "Content-Length": str(len(zip_buf.getvalue()))
        }
        return StreamingResponse(zip_buf, media_type="application/zip", headers=headers)
    except Exception as e:
        return {"error": f"ZIP package generation failed: {str(e)}"}