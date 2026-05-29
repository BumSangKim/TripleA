from __future__ import annotations

from fastapi import Depends

from api.features.auth.repository import AuthRepository
from api.features.auth.service import AuthService


def get_auth_repository() -> AuthRepository:
    return AuthRepository()


def get_auth_service(
    repo: AuthRepository = Depends(get_auth_repository),
) -> AuthService:
    return AuthService(repo)
