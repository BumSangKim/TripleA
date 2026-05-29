from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.features.auth.dependencies import get_auth_service
from api.features.auth.schemas import TokenResponse
from api.features.auth.service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
):
    token = service.authenticate(form_data.username, form_data.password)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 실패")
    return TokenResponse(access_token=token.access_token)
