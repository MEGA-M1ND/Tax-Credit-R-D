import os
import json
from fastapi import Header, HTTPException
from typing import Optional
from .review_models import ReviewerRole, can_approve_reject, can_override

# Example in .env:
# VALID_API_KEYS=admin123,analyst456,reviewer789
VALID_KEYS = [k.strip() for k in os.getenv("VALID_API_KEYS", "").split(",") if k.strip()]

# Example in .env:
# USER_ROLES={"admin":"ADMIN","reviewer":"REVIEWER","analyst":"ANALYST","tax_manager":"TAX_MANAGER"}
ROLE_MAP = json.loads(os.getenv("USER_ROLES", "{}"))


def enforce_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")) -> str:
    """
    Basic API-key authentication.
    Fails closed if keys are not configured or invalid.
    """
    if not VALID_KEYS:
        raise HTTPException(status_code=500, detail="API keys not configured")

    if x_api_key is None or x_api_key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    return x_api_key


def get_role(api_key: Optional[str]) -> Optional[ReviewerRole]:
    """Look up the role associated with a given API key."""
    if api_key is None:
        return None
    for role_str, key in ROLE_MAP.items():
        if key == api_key:
            try:
                return ReviewerRole(role_str)
            except ValueError:
                return None
    return None


def get_role_from_api_key(api_key: Optional[str]) -> Optional[ReviewerRole]:
    """
    Alias for get_role() for clarity.
    Converts API key to ReviewerRole enum.
    """
    return get_role(api_key)


def require_role(required_role: str):
    """
    Dependency factory enforcing that the caller has a specific role.
    Usage: Depends(require_role("REVIEWER"))
    """

    def dependency(x_api_key: str = Header(default=None, alias="X-API-Key")) -> ReviewerRole:
        if not ROLE_MAP:
            raise HTTPException(status_code=500, detail="USER_ROLES not configured")
        role = get_role(x_api_key)
        if role is None or role.value != required_role:
            raise HTTPException(status_code=403, detail=f"Role '{role}' cannot access this resource")
        return role

    return dependency


def require_approve_reject(x_api_key: str = Header(default=None, alias="X-API-Key")) -> ReviewerRole:
    """
    Dependency enforcing that the caller can approve/reject.
    """
    if not ROLE_MAP:
        raise HTTPException(status_code=500, detail="USER_ROLES not configured")
    role = get_role(x_api_key)
    if role is None or not can_approve_reject(role):
        raise HTTPException(status_code=403, detail=f"Role '{role}' cannot approve/reject. Required: REVIEWER or higher.")
    return role


def require_override(x_api_key: str = Header(default=None, alias="X-API-Key")) -> ReviewerRole:
    """
    Dependency enforcing that the caller can override.
    """
    if not ROLE_MAP:
        raise HTTPException(status_code=500, detail="USER_ROLES not configured")
    role = get_role(x_api_key)
    if role is None or not can_override(role):
        raise HTTPException(status_code=403, detail=f"Role '{role}' cannot override. Required: DIRECTOR, PARTNER, or ADMIN.")
    return role