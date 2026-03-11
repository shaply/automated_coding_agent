"""
Bearer token authentication middleware for FastAPI.
Every endpoint requires Authorization: Bearer <AUTODEV_API_TOKEN>.
No exceptions — the agent holds GitHub credentials and can push code.

SSE note: EventSource cannot send headers, so the stream endpoint also
accepts the token via ?token= query parameter.
"""

import os
from fastapi import Request, HTTPException


def get_api_token() -> str:
    token = os.environ.get("AUTODEV_API_TOKEN", "")
    if not token:
        raise RuntimeError("AUTODEV_API_TOKEN is not set in the environment.")
    return token


async def verify_token(request: Request) -> None:
    """
    Dependency for FastAPI routes.
    Accepts Bearer token in Authorization header OR ?token= query param.
    The query param fallback is required for SSE (EventSource can't send headers).
    """
    expected = get_api_token()

    # 1. Try Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        if token == expected:
            return
        raise HTTPException(status_code=401, detail="Invalid API token.")

    # 2. Fall back to ?token= query param (for SSE clients)
    token = request.query_params.get("token", "")
    if token == expected:
        return

    raise HTTPException(status_code=401, detail="Missing or invalid token.")
