"""
Storage layer for review records using SQLite.

This module provides:
1. Database initialization and management
2. CRUD operations for review records
3. Status resolution (get current state)
4. Transition validation
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

from .review_models import (
    ReviewStatus,
    ReviewerRole,
    ReviewRecord,
    ReviewState,
    validate_transition,
)


# ============================================================================
# Configuration
# ============================================================================

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "reviews.db"


def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Database Management
# ============================================================================

class ReviewStorage:
    """
    SQLite-based storage for review records.
    
    Uses append-only pattern: each review action creates a new row.
    The "current" state is determined by the most recent row per project.
    """
    
    def __init__(self, db_path: str = str(DB_PATH)):
        ensure_data_dir()
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection to the database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create project_reviews table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_reviews (
                    review_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reviewer_name TEXT NOT NULL,
                    reviewer_role TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    source_decision INTEGER,
                    source_confidence REAL,
                    source_trace_path TEXT,
                    review_trace_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_project_id
                ON project_reviews(project_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON project_reviews(timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON project_reviews(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_project_timestamp
                ON project_reviews(project_id, timestamp DESC)
            """)
            
            conn.commit()
    
    # ========================================================================
    # CRUD Operations
    # ========================================================================
    
    def create_review(self, record: ReviewRecord) -> ReviewRecord:
        """
        Create a new review record (append-only).
        
        Returns the created record with timestamp set.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO project_reviews (
                    review_id,
                    project_id,
                    status,
                    reviewer_name,
                    reviewer_role,
                    reason,
                    timestamp,
                    source_decision,
                    source_confidence,
                    source_trace_path,
                    review_trace_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.review_id,
                record.project_id,
                record.status.value,
                record.reviewer_name,
                record.reviewer_role.value,
                record.reason,
                record.timestamp.isoformat(),
                record.source_decision,
                record.source_confidence,
                record.source_trace_path,
                record.review_trace_path,
            ))
            conn.commit()
        
        return record

    def update_review_trace(self, review_id: str, trace_path: str) -> None:
        """Update review record with generated trace path."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE project_reviews
                SET review_trace_path=?
                WHERE review_id=?
                """,
                (trace_path, review_id),
            )
            conn.commit()
    
    def get_review(self, review_id: str) -> Optional[ReviewRecord]:
        """Retrieve a single review by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM project_reviews WHERE review_id = ?
            """, (review_id,))
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return self._row_to_record(row)
    
    def get_project_history(self, project_id: str) -> List[ReviewRecord]:
        """
        Get all reviews for a project in chronological order (oldest first).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM project_reviews
                WHERE project_id = ?
                ORDER BY timestamp ASC
            """, (project_id,))
            rows = cursor.fetchall()
        
        return [self._row_to_record(row) for row in rows]
    
    def get_latest_review(self, project_id: str) -> Optional[ReviewRecord]:
        """Get the most recent review for a project."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM project_reviews
                WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (project_id,))
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return self._row_to_record(row)
    
    def get_review_queue(
        self,
        statuses: Optional[List[ReviewStatus]] = None,
        limit: int = 100
    ) -> List[Tuple[str, ReviewState]]:
        """
        Get projects needing review (those in MANUAL_REVIEW, RECOMMENDED_*, or unreviewed).
        
        Returns a list of (project_id, state) tuples sorted by confidence ascending
        (lowest confidence first = most uncertain = review first).
        
        Args:
            statuses: If provided, filter to these statuses. Defaults to manual review items.
            limit: Maximum number of results.
        
        Returns:
            List of (project_id, ReviewState) tuples.
        """
        if statuses is None:
            statuses = [
                ReviewStatus.MANUAL_REVIEW,
                ReviewStatus.RECOMMENDED_ELIGIBLE,
                ReviewStatus.RECOMMENDED_NOT_ELIGIBLE,
            ]
        
        status_values = [s.value for s in statuses]
        placeholders = ",".join("?" * len(status_values))
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT 
                    project_id,
                    status,
                    reviewer_name,
                    reviewer_role,
                    reason,
                    timestamp,
                    source_decision,
                    source_confidence,
                    source_trace_path,
                    review_trace_path
                FROM project_reviews
                WHERE status IN ({placeholders})
                ORDER BY source_confidence ASC, timestamp DESC
                LIMIT ?
            """, status_values + [limit])
            rows = cursor.fetchall()
        
        # Build a map of project_id -> latest state
        project_states = {}
        for row in rows:
            project_id = row["project_id"]
            if project_id not in project_states:
                project_states[project_id] = self._row_to_record(row)
        
        # Get full history for each project
        results = []
        for project_id, latest in project_states.items():
            history = self.get_project_history(project_id)
            state = ReviewState(
                project_id=project_id,
                current_status=latest.status,
                last_review=latest,
                history=history,
            )
            results.append((project_id, state))
        
        return results
    
    # ========================================================================
    # Status Resolution & Validation
    # ========================================================================
    
    def get_current_review_state(self, project_id: str) -> ReviewState:
        """
        Get the current review state for a project.
        
        Logic:
        - Query the latest review by timestamp DESC
        - If none exists, state is UNREVIEWED (MANUAL_REVIEW)
        """
        latest = self.get_latest_review(project_id)
        history = self.get_project_history(project_id)
        
        if not latest:
            return ReviewState(
                project_id=project_id,
                current_status=ReviewStatus.MANUAL_REVIEW,
                last_review=None,
                history=[],
            )
        
        return ReviewState(
            project_id=project_id,
            current_status=latest.status,
            last_review=latest,
            history=history,
        )
    
    def validate_and_create_review(
        self,
        project_id: str,
        new_status: ReviewStatus,
        reviewer_name: str,
        reviewer_role: ReviewerRole,
        reason: str,
        source_decision: Optional[bool] = None,
        source_confidence: Optional[float] = None,
        source_trace_path: Optional[str] = None,
        review_trace_path: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[ReviewRecord]]:
        """
        Validate a transition and create a review record if valid.
        
        Returns:
            (success: bool, error_message: Optional[str], record: Optional[ReviewRecord])
        """
        # Get current state
        current_state = self.get_current_review_state(project_id)
        
        # Validate transition
        is_valid, error_msg = validate_transition(
            current_state.current_status,
            new_status,
            reviewer_role,
        )
        
        if not is_valid:
            return False, error_msg, None
        
        # Additional safety checks
        if new_status in (ReviewStatus.REJECTED, ReviewStatus.OVERRIDDEN):
            if len(reason) < 20:
                return False, f"Reason must be at least 20 characters for {new_status}.", None
        
        # Create the record
        import uuid
        record = ReviewRecord(
            review_id=str(uuid.uuid4()),
            project_id=project_id,
            status=new_status,
            reviewer_name=reviewer_name,
            reviewer_role=reviewer_role,
            reason=reason,
            timestamp=datetime.utcnow(),
            source_decision=source_decision,
            source_confidence=source_confidence,
            source_trace_path=source_trace_path,
            review_trace_path=review_trace_path,
        )
        
        # Store it
        created = self.create_review(record)
        return True, None, created
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ReviewRecord:
        """Convert a database row to a ReviewRecord."""
        return ReviewRecord(
            review_id=row["review_id"],
            project_id=row["project_id"],
            status=ReviewStatus(row["status"]),
            reviewer_name=row["reviewer_name"],
            reviewer_role=ReviewerRole(row["reviewer_role"]),
            reason=row["reason"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            source_decision=bool(row["source_decision"]) if row["source_decision"] is not None else None,
            source_confidence=row["source_confidence"],
            source_trace_path=row["source_trace_path"],
            review_trace_path=row["review_trace_path"],
        )
    
    def export_to_dict(self, project_id: str) -> dict:
        """Export project review history as a dictionary."""
        state = self.get_current_review_state(project_id)
        return {
            "project_id": project_id,
            "current_status": state.current_status.value,
            "last_review": state.last_review.dict() if state.last_review else None,
            "history": [r.dict() for r in state.history],
        }


# ============================================================================
# Global Storage Instance
# ============================================================================

# Create a global instance for easy access
_storage_instance: Optional[ReviewStorage] = None


def get_storage() -> ReviewStorage:
    """Get the global storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ReviewStorage()
    return _storage_instance


def init_storage(db_path: str = str(DB_PATH)):
    """Initialize or reset the storage with a specific DB path."""
    global _storage_instance
    _storage_instance = ReviewStorage(db_path)
    return _storage_instance
