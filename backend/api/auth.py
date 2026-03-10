"""
Bearer token authentication middleware for FastAPI.
Every endpoint requires Authorization: Bearer <AUTODEV_API_TOKEN>.
No exceptions — the agent holds GitHub credentials and can push code.
"""

import os
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_security = HTTPBearer()


def get_api_token() -> str:
    token = os.environ.get("AUTODEV_API_TOKEN", "")
    if not token:
        raise RuntimeError("AUTODEV_API_TOKEN is not set in the environment.")
    return token


async def verify_token(request: Request) -> None:
    """
    Dependency for FastAPI routes.
    Usage: router.add_api_route(..., dependencies=[Depends(verify_token)])
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = auth_header.removeprefix("Bearer ").strip()
    if token != get_api_token():
        raise HTTPException(status_code=401, detail="Invalid API token.")
