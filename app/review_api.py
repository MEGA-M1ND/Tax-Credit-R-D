"""
Review API endpoints for R&D Tax Credit classification system.

Provides:
- GET /reviews/{project_id} - Get review state + history
- POST /reviews/{project_id}/action - Create a new review action
- GET /reviews/queue - Get projects needing review
- GET /reviews/{project_id}/report - Get review report
"""

import logging

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime

from .review_models import (
    ReviewStatus,
    ReviewerRole,
    ReviewActionCreate,
    ReviewState,
    ReviewReportResponse,
)
from .storage import get_storage, ReviewStorage
from .trace_logger import ImmutableTraceLogger
from .auth import require_approve_reject, require_override, get_role_from_api_key
from .form_lock_store import record_review_action


# Router for review endpoints
review_router = APIRouter(prefix="/reviews", tags=["reviews"])

# Global trace logger
trace_logger = ImmutableTraceLogger()
logger = logging.getLogger(__name__)


# ============================================================================
# GET /reviews/{project_id}
# ============================================================================

@review_router.get("/{project_id}", response_model=ReviewState)
def get_review_state(project_id: str) -> ReviewState:
    """
    Get the current review state and history for a project.
    
    Returns:
        ReviewState with current status and full history
    """
    storage = get_storage()
    state = storage.get_current_review_state(project_id)
    return state


# ============================================================================
# POST /reviews/{project_id}/action
# ============================================================================

@review_router.post("/{project_id}/action", response_model=ReviewState)
def create_review_action(
    project_id: str,
    action: ReviewActionCreate,
    x_api_key: str = Header(default=None, alias="X-API-Key"),
) -> ReviewState:
    """
    Create a new review action (approve, reject, or override).
    
    Required permissions:
    - APPROVE/REJECT: REVIEWER role or higher
    - OVERRIDE: DIRECTOR/PARTNER/ADMIN role
    
    Args:
        project_id: Project being reviewed
        action: ReviewActionCreate with status, reviewer_name, role, reason
    
    Returns:
        Updated ReviewState
    
    Raises:
        403: If role doesn't have permission for the action
        400: If transition is invalid or reason too short
    """
    # Get reviewer role
    role = get_role_from_api_key(x_api_key)
    if role is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    
    storage = get_storage()
    
    # Permission checks will be in validate_and_create_review
    # But we can do early role checks here for better UX
    if action.status in (ReviewStatus.APPROVED, ReviewStatus.REJECTED):
        # Require approve/reject permission
        from .review_models import can_approve_reject
        if not can_approve_reject(action.reviewer_role):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{action.reviewer_role}' cannot approve/reject. Required: REVIEWER or higher."
            )
    
    if action.status == ReviewStatus.OVERRIDDEN:
        # Require override permission
        from .review_models import can_override
        if not can_override(action.reviewer_role):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{action.reviewer_role}' cannot override. Required: DIRECTOR, PARTNER, or ADMIN."
            )
    
    # Get current state for trace
    current_state = storage.get_current_review_state(project_id)
    old_status = current_state.current_status or "UNREVIEWED"
    
    # Validate and create review
    success, error_msg, review_record = storage.validate_and_create_review(
        project_id=project_id,
        new_status=action.status,
        reviewer_name=action.reviewer_name,
        reviewer_role=action.reviewer_role,
        reason=action.reason,
        source_decision=current_state.last_review.source_decision if current_state.last_review else None,
        source_confidence=current_state.last_review.source_confidence if current_state.last_review else None,
        source_trace_path=current_state.last_review.source_trace_path if current_state.last_review else None,
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Write review action trace
    review_trace_path = trace_logger.write_review_trace(
        project_id=project_id,
        reviewer_name=action.reviewer_name,
        reviewer_role=action.reviewer_role.value,
        old_status=old_status.value if hasattr(old_status, 'value') else old_status,
        new_status=action.status.value,
        reason=action.reason,
        additional_data={"review_id": review_record.review_id},
    )
    
    # Update the review record with the trace path
    review_record.review_trace_path = review_trace_path
    storage.update_review_trace(review_record.review_id, review_trace_path)

    try:
        record_review_action(
            review_id=review_record.review_id,
            project_id=review_record.project_id,
            status=review_record.status.value,
            reviewer_name=review_record.reviewer_name,
            reviewer_role=review_record.reviewer_role.value,
            reason=review_record.reason,
            created_at_utc=review_record.timestamp.isoformat(),
            source_confidence=review_record.source_confidence,
            source_trace_path=review_record.source_trace_path,
            review_trace_path=review_record.review_trace_path,
        )
    except Exception as exc:
        # Defer to operators if secondary persistence fails; core review already stored.
        logger.exception("Failed to mirror review action into form lock store: %s", exc)
    
    # Return updated state
    return storage.get_current_review_state(project_id)


# ============================================================================
# GET /reviews/queue
# ============================================================================

@review_router.get("/queue", response_model=dict)
def get_review_queue(
    status: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """
    Get projects needing review.
    
    Filters:
    - status: Optional comma-separated statuses (defaults to MANUAL_REVIEW, RECOMMENDED_*)
    - limit: Maximum results
    
    Results sorted by confidence ascending (lowest confidence = review first).
    
    Returns:
        Dict with 'count' and 'queue' (list of projects needing review)
    """
    storage = get_storage()
    
    # Parse status filter
    statuses = None
    if status:
        status_strs = [s.strip() for s in status.split(",")]
        try:
            statuses = [ReviewStatus(s) for s in status_strs]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid status: {e}")
    
    # Get queue
    queue_items = storage.get_review_queue(statuses=statuses, limit=limit)
    
    return {
        "count": len(queue_items),
        "queue": [
            {
                "project_id": project_id,
                "current_status": state.current_status.value,
                "confidence": state.last_review.source_confidence if state.last_review else None,
                "last_review_timestamp": state.last_review.timestamp.isoformat() if state.last_review else None,
                "reason": state.last_review.reason if state.last_review else None,
            }
            for project_id, state in queue_items
        ]
    }


# ============================================================================
# GET /reviews/{project_id}/report
# ============================================================================

@review_router.get("/{project_id}/report", response_model=ReviewReportResponse)
def get_review_report(project_id: str) -> ReviewReportResponse:
    """
    Get a review report for a project.
    
    Includes:
    - Final status and decision
    - Reviewer identity
    - AI recommendation and confidence
    - Trace references
    
    Returns:
        ReviewReportResponse with complete review information
    """
    storage = get_storage()
    state = storage.get_current_review_state(project_id)
    
    last_review = state.last_review
    if not last_review:
        raise HTTPException(status_code=404, detail=f"No review found for project {project_id}")
    
    # Infer final decision from status
    final_decision = None
    if last_review.status == ReviewStatus.APPROVED:
        final_decision = last_review.source_decision
    elif last_review.status == ReviewStatus.REJECTED:
        final_decision = False
    elif last_review.status == ReviewStatus.OVERRIDDEN:
        # Infer from context - if there was an APPROVED before, it was overridden
        final_decision = None  # Could be either, context-dependent
    
    # Determine AI recommendation
    ai_recommendation = None
    if last_review.source_decision is True:
        ai_recommendation = ReviewStatus.RECOMMENDED_ELIGIBLE
    elif last_review.source_decision is False:
        ai_recommendation = ReviewStatus.RECOMMENDED_NOT_ELIGIBLE
    
    return ReviewReportResponse(
        project_id=project_id,
        final_status=state.current_status,
        final_decision=final_decision,
        reviewer_name=last_review.reviewer_name,
        reviewer_role=last_review.reviewer_role,
        timestamp=last_review.timestamp,
        reason=last_review.reason,
        ai_recommendation=ai_recommendation,
        ai_confidence=last_review.source_confidence,
        ai_trace_path=last_review.source_trace_path,
        review_trace_path=last_review.review_trace_path,
    )


# ============================================================================
# Helper: Add to main.py or create a separate app
# ============================================================================

def setup_review_routes(app):
    """
    Helper function to add review routes to a FastAPI app.
    
    Usage in main.py:
        from .review_api import setup_review_routes
        setup_review_routes(app)
    """
    app.include_router(review_router)
