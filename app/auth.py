"""API-key auth (a stand-in for OAuth2/JWT in the demo)."""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

DEFAULT_KEY = "dev-key"


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("SERVICE_API_KEY", DEFAULT_KEY)
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid X-API-Key",
        )
