"""
Review workflow models for R&D Tax Credit classification system.

This module defines:
1. ReviewStatus enum (canonical review statuses)
2. ReviewerRole enum (user roles with permissions)
3. Pydantic models for review records and actions
4. Transition rules (hard rules for status transitions)
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


# ============================================================================
# Step 0: Workflow Contract - Statuses & Roles
# ============================================================================

class ReviewStatus(str, Enum):
    """Canonical review statuses for R&D Tax Credit classification."""
    
    RECOMMENDED_ELIGIBLE = "RECOMMENDED_ELIGIBLE"
    RECOMMENDED_NOT_ELIGIBLE = "RECOMMENDED_NOT_ELIGIBLE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"


class ReviewerRole(str, Enum):
    """Role definitions with permission hierarchy."""
    
    ANALYST = "ANALYST"                 # Can view + optionally recommend
    REVIEWER = "REVIEWER"               # Can approve/reject
    TAX_MANAGER = "TAX_MANAGER"         # Can approve/reject (same as REVIEWER)
    DIRECTOR = "DIRECTOR"               # Can override (highest permission)
    PARTNER = "PARTNER"                 # Can override (co-highest permission)
    ADMIN = "ADMIN"                     # Can override + manage system


# ============================================================================
# Step 0: Transition Rules (Hard Rules)
# ============================================================================

# Allowed transitions: key=current_status, value=list of allowed next statuses
ALLOWED_TRANSITIONS = {
    ReviewStatus.RECOMMENDED_ELIGIBLE: [
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.OVERRIDDEN,
    ],
    ReviewStatus.RECOMMENDED_NOT_ELIGIBLE: [
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.OVERRIDDEN,
    ],
    ReviewStatus.MANUAL_REVIEW: [
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.OVERRIDDEN,
    ],
    ReviewStatus.APPROVED: [
        ReviewStatus.OVERRIDDEN,  # Can only override an approval
    ],
    ReviewStatus.REJECTED: [
        ReviewStatus.OVERRIDDEN,  # Can only override a rejection
    ],
    ReviewStatus.OVERRIDDEN: [
        # OVERRIDDEN is final; cannot change
    ],
}


# Role hierarchy for permission checks
ROLE_HIERARCHY = {
    ReviewerRole.ANALYST: 0,
    ReviewerRole.REVIEWER: 1,
    ReviewerRole.TAX_MANAGER: 1,  # Same level as REVIEWER
    ReviewerRole.DIRECTOR: 2,
    ReviewerRole.PARTNER: 2,      # Same level as DIRECTOR
    ReviewerRole.ADMIN: 3,        # Highest level
}


def can_approve_reject(role: ReviewerRole) -> bool:
    """Check if a role can APPROVE or REJECT."""
    return ROLE_HIERARCHY.get(role, -1) >= 1


def can_override(role: ReviewerRole) -> bool:
    """Check if a role can OVERRIDE."""
    return ROLE_HIERARCHY.get(role, -1) >= 2


def validate_transition(
    current_status: ReviewStatus,
    new_status: ReviewStatus,
    reviewer_role: ReviewerRole,
) -> tuple[bool, Optional[str]]:
    """
    Validate a status transition.
    
    Returns:
        (is_valid: bool, error_message: Optional[str])
    """
    # Special case: None or UNREVIEWED means no current state
    if current_status is None or current_status == "UNREVIEWED":
        current_status = ReviewStatus.MANUAL_REVIEW
    
    # Check if transition is allowed
    if current_status not in ALLOWED_TRANSITIONS:
        return False, f"Unknown current status: {current_status}"
    
    allowed_next = ALLOWED_TRANSITIONS[current_status]
    if new_status not in allowed_next:
        return False, f"Cannot transition from {current_status} to {new_status}. Allowed: {allowed_next}"
    
    # Check role permissions
    if new_status in (ReviewStatus.APPROVED, ReviewStatus.REJECTED):
        if not can_approve_reject(reviewer_role):
            return False, f"Role {reviewer_role} cannot approve/reject. Required: REVIEWER or higher."
    
    if new_status == ReviewStatus.OVERRIDDEN:
        if not can_override(reviewer_role):
            return False, f"Role {reviewer_role} cannot override. Required: DIRECTOR, PARTNER, or ADMIN."
    
    return True, None


# ============================================================================
# Step 1: Pydantic Models for Reviews
# ============================================================================

class ReviewActionCreate(BaseModel):
    """Incoming review action request."""
    
    status: ReviewStatus = Field(..., description="New review status")
    reviewer_name: str = Field(..., min_length=1, description="Name of the reviewer")
    reviewer_role: ReviewerRole = Field(..., description="Role of the reviewer")
    reason: str = Field(..., min_length=1, description="Reason for this action")


class ReviewRecord(BaseModel):
    """Stored review record (immutable append-only)."""
    
    review_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    status: ReviewStatus
    reviewer_name: str
    reviewer_role: ReviewerRole
    reason: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_decision: Optional[bool] = Field(None, description="AI decision (True=eligible, False=not_eligible)")
    source_confidence: Optional[float] = Field(None, ge=0, le=1, description="AI confidence score")
    source_trace_path: Optional[str] = Field(None, description="Path to AI trace file")
    review_trace_path: Optional[str] = Field(None, description="Path to review action trace file")


class ReviewState(BaseModel):
    """Current review state for a project."""
    
    project_id: str
    current_status: ReviewStatus = ReviewStatus.MANUAL_REVIEW
    last_review: Optional[ReviewRecord] = None
    history: List[ReviewRecord] = Field(default_factory=list)


class ReviewReportResponse(BaseModel):
    """Report for a single review decision."""
    
    project_id: str
    final_status: ReviewStatus
    final_decision: Optional[bool] = Field(None, description="Final eligibility decision")
    reviewer_name: Optional[str] = None
    reviewer_role: Optional[ReviewerRole] = None
    timestamp: Optional[datetime] = None
    reason: Optional[str] = None
    ai_recommendation: Optional[ReviewStatus] = None
    ai_confidence: Optional[float] = None
    ai_trace_path: Optional[str] = None
    review_trace_path: Optional[str] = None
