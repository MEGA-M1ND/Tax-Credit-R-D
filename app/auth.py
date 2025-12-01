import os
import json
from fastapi import Header, HTTPException

# Example in .env:
# VALID_API_KEYS=admin123,analyst456,reviewer789
VALID_KEYS = [k.strip() for k in os.getenv("VALID_API_KEYS", "").split(",") if k.strip()]

# Example in .env:
# USER_ROLES={"admin":"admin123","reviewer":"reviewer789","analyst":"analyst456"}
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


def get_role(api_key: str | None) -> str | None:
    """Look up the role associated with a given API key."""
    if api_key is None:
        return None
    for role, key in ROLE_MAP.items():
        if key == api_key:
            return role
    return None


def require_role(required_role: str):
    """
    Dependency factory enforcing that the caller has a specific role.
    Usage: Depends(require_role("reviewer"))
    """

    def dependency(x_api_key: str = Header(default=None, alias="X-API-Key")) -> str:
        if not ROLE_MAP:
            raise HTTPException(status_code=500, detail="USER_ROLES not configured")
        role = get_role(x_api_key)
        if role != required_role:
            raise HTTPException(status_code=403, detail=f"Role '{role}' cannot access this resource")
        return role

    return dependency