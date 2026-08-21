from __future__ import annotations

import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def get_api_key() -> str:
    return os.getenv("API_KEY", "dev-local-key")


def require_bearer(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    expected = get_api_key()
    if creds is None or creds.scheme.lower() != "bearer" or creds.credentials != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid internal auth token")
    return creds.credentials
