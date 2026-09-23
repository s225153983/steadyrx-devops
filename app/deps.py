"""FastAPI dependencies for services and authentication."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services import SteadyRxService

bearer = HTTPBearer(auto_error=False)


def get_service(request: Request) -> SteadyRxService:
    return request.app.state.service


def current_user(request: Request,
                 creds: HTTPAuthorizationCredentials | None = Depends(bearer)
                 ) -> dict:
    """Return the token claims or reject the request with 401."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        return request.app.state.decode(creds.credentials)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token",
                            headers={"WWW-Authenticate": "Bearer"}) from exc


def require_pharmacist(user: dict = Depends(current_user)) -> dict:
    """Only pharmacists may change clinical records or review alerts."""
    if user.get("role") != "pharmacist":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Pharmacist role needed")
    return user
