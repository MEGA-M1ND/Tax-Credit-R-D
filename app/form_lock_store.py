"""Review → Form lock mechanism.

Purpose:
- Freeze approved projects into an eligibility snapshot.
- Prevent silent regeneration of forms after approvals.
- Support explicit re-generation only via override action.

Implementation:
- SQLite append-only tables.
- Eligibility snapshot hash links to approved review records.
- Form versioning with immutable hashes.
"""

from __future__ import annotations

import os
import json
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

DB_PATH = os.environ.get("RND_AGENT_DB", os.path.join(os.path.dirname(__file__), "data", "agent.db"))


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def init_db(db_path: str = DB_PATH) -> None:
    _ensure_dir(db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Review actions table (append-only). If you already created one, keep schema aligned.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS review_actions (
            review_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            status TEXT NOT NULL,
            reviewer_name TEXT NOT NULL,
            reviewer_role TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            source_confidence REAL,
            source_trace_path TEXT,
            review_trace_path TEXT
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_review_project ON review_actions(project_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_review_created ON review_actions(created_at_utc);")

    # Eligibility snapshot (frozen approved projects)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS eligibility_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            tax_year INTEGER NOT NULL,
            snapshot_sha256 TEXT NOT NULL,
            approved_projects_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            created_by TEXT NOT NULL
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snap_tax_year ON eligibility_snapshots(tax_year);")

    # Form versions (immutable)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS form_versions (
            form_version_id TEXT PRIMARY KEY,
            tax_year INTEGER NOT NULL,
            snapshot_id TEXT NOT NULL,
            form_sha256 TEXT NOT NULL,
            form_json TEXT NOT NULL,
            pdf_path TEXT,
            created_at_utc TEXT NOT NULL,
            created_by TEXT NOT NULL,
            FOREIGN KEY(snapshot_id) REFERENCES eligibility_snapshots(snapshot_id)
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_form_tax_year ON form_versions(tax_year);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_form_snapshot ON form_versions(snapshot_id);")

    # Form lock: one active form per (tax_year) unless overridden
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS form_locks (
            lock_id TEXT PRIMARY KEY,
            tax_year INTEGER NOT NULL,
            active_form_version_id TEXT NOT NULL,
            locked_at_utc TEXT NOT NULL,
            locked_by TEXT NOT NULL,
            lock_reason TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lock_tax_year ON form_locks(tax_year);")

    con.commit()
    con.close()


def get_latest_review_status(db_path: str, project_id: str) -> Optional[str]:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """SELECT status FROM review_actions WHERE project_id=? ORDER BY created_at_utc DESC LIMIT 1""",
        (project_id,),
    )
    row = cur.fetchone()
    con.close()
    return row[0] if row else None


def list_approved_projects(db_path: str, project_ids: List[str]) -> List[str]:
    approved = []
    for pid in project_ids:
        st = get_latest_review_status(db_path, pid)
        if st == "APPROVED":
            approved.append(pid)
    return approved


def create_eligibility_snapshot(
    *,
    db_path: str = DB_PATH,
    tax_year: int,
    project_ids: List[str],
    created_by: str,
    snapshot_id: Optional[str] = None,
    approved_project_ids: Optional[List[str]] = None,
) -> Tuple[str, str, List[str]]:
    """Freeze approved projects into a snapshot.

    Returns: (snapshot_id, snapshot_sha256, approved_project_ids)
    """
    import uuid

    init_db(db_path)
    if approved_project_ids is not None:
        approved_sorted = sorted(set(approved_project_ids))
    else:
        approved = list_approved_projects(db_path, project_ids)
        approved_sorted = sorted(set(approved))
    payload = {"tax_year": tax_year, "approved_project_ids": approved_sorted}
    sha = _sha256(payload)
    sid = snapshot_id or f"snap_{tax_year}_{sha[:12]}"

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO eligibility_snapshots
        (snapshot_id, tax_year, snapshot_sha256, approved_projects_json, created_at_utc, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sid, tax_year, sha, json.dumps(approved_sorted), _utc_now(), created_by),
    )
    con.commit()
    con.close()

    return sid, sha, approved_sorted


def get_active_form_lock(db_path: str, tax_year: int) -> Optional[Dict[str, Any]]:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
        SELECT lock_id, active_form_version_id, locked_at_utc, locked_by, lock_reason, is_active
        FROM form_locks
        WHERE tax_year=? AND is_active=1
        ORDER BY locked_at_utc DESC
        LIMIT 1
        """,
        (tax_year,),
    )
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return {
        "lock_id": row[0],
        "active_form_version_id": row[1],
        "locked_at_utc": row[2],
        "locked_by": row[3],
        "lock_reason": row[4],
        "is_active": bool(row[5]),
    }


def lock_form_version(
    *,
    db_path: str = DB_PATH,
    tax_year: int,
    form_version_id: str,
    locked_by: str,
    lock_reason: str,
) -> str:
    import uuid

    init_db(db_path)
    # deactivate existing lock
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("UPDATE form_locks SET is_active=0 WHERE tax_year=? AND is_active=1", (tax_year,))
    lock_id = f"lock_{tax_year}_{uuid.uuid4().hex[:8]}"
    cur.execute(
        """
        INSERT INTO form_locks
        (lock_id, tax_year, active_form_version_id, locked_at_utc, locked_by, lock_reason, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (lock_id, tax_year, form_version_id, _utc_now(), locked_by, lock_reason),
    )
    con.commit()
    con.close()
    return lock_id


def save_form_version(
    *,
    db_path: str = DB_PATH,
    tax_year: int,
    snapshot_id: str,
    form_version_id: str,
    form_sha256: str,
    form_json: Dict[str, Any],
    created_by: str,
    pdf_path: Optional[str] = None,
) -> None:
    init_db(db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO form_versions
        (form_version_id, tax_year, snapshot_id, form_sha256, form_json, pdf_path, created_at_utc, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (form_version_id, tax_year, snapshot_id, form_sha256, json.dumps(form_json), pdf_path, _utc_now(), created_by),
    )
    con.commit()
    con.close()


def get_form_version(db_path: str, form_version_id: str) -> Optional[Dict[str, Any]]:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """SELECT form_version_id, tax_year, snapshot_id, form_sha256, form_json, pdf_path, created_at_utc, created_by
           FROM form_versions WHERE form_version_id=?""",
        (form_version_id,),
    )
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return {
        "form_version_id": row[0],
        "tax_year": row[1],
        "snapshot_id": row[2],
        "form_sha256": row[3],
        "form_json": json.loads(row[4] or "{}"),
        "pdf_path": row[5],
        "created_at_utc": row[6],
        "created_by": row[7],
    }

def record_review_action(
    *,
    db_path: str = DB_PATH,
    review_id: str,
    project_id: str,
    status: str,
    reviewer_name: str,
    reviewer_role: str,
    reason: str,
    created_at_utc: str,
    source_confidence: Optional[float] = None,
    source_trace_path: Optional[str] = None,
    review_trace_path: Optional[str] = None,
) -> None:
    """Persist a review action in the form-lock database."""

    init_db(db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO review_actions (
            review_id,
            project_id,
            status,
            reviewer_name,
            reviewer_role,
            reason,
            created_at_utc,
            source_confidence,
            source_trace_path,
            review_trace_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review_id,
            project_id,
            status,
            reviewer_name,
            reviewer_role,
            reason,
            created_at_utc,
            source_confidence,
            source_trace_path,
            review_trace_path,
        ),
    )
    con.commit()
    con.close()


def get_snapshot(db_path: str, snapshot_id: str) -> Optional[Dict[str, Any]]:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
        SELECT snapshot_id, tax_year, snapshot_sha256, approved_projects_json, created_at_utc, created_by
        FROM eligibility_snapshots
        WHERE snapshot_id=?
        """,
        (snapshot_id,),
    )
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return {
        "snapshot_id": row[0],
        "tax_year": row[1],
        "snapshot_sha256": row[2],
        "approved_project_ids": json.loads(row[3] or "[]"),
        "created_at_utc": row[4],
        "created_by": row[5],
    }
