"""Authentication boundary. No placeholder tokens or permissive authorization."""
from fastapi import HTTPException, status


def require_user():
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Authentication not implemented")
