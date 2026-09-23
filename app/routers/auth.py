"""Login endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.deps import get_service
from app.metrics import LOGIN_FAILURES
from app.schemas import LoginRequest, TokenResponse
from app.security import create_token, verify_password
from app.services import SteadyRxService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request,
          service: SteadyRxService = Depends(get_service)) -> TokenResponse:
    rows = service.db.query("SELECT * FROM users WHERE username=?",
                            (body.username,))
    if not rows or not verify_password(body.password, rows[0]["password_hash"]):
        LOGIN_FAILURES.inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Incorrect username or password")
    user = rows[0]
    settings = request.app.state.settings
    token = create_token(user["username"], user["role"], settings.jwt_secret,
                         settings.jwt_ttl_minutes)
    service.db.audit(user["username"], "auth.login", {})
    return TokenResponse(access_token=token, role=user["role"])
