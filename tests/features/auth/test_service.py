from __future__ import annotations

import ast
from pathlib import Path

import pytest

from api.features.auth.models import AuthToken
from api.features.auth.ports import ICredentialStore
from api.features.auth.service import AuthService


class FakeCredentialStore:
    def __init__(self, valid: bool = True):
        self._valid = valid

    def verify(self, username: str, password: str) -> bool:
        return self._valid


def test_authenticate_valid_credentials_returns_token():
    service = AuthService(FakeCredentialStore(valid=True))
    token = service.authenticate("admin", "secret")
    assert token is not None
    assert isinstance(token, AuthToken)
    assert token.access_token


def test_authenticate_invalid_credentials_returns_none():
    service = AuthService(FakeCredentialStore(valid=False))
    token = service.authenticate("admin", "wrong")
    assert token is None


def test_repository_import_smoke():
    from api.features.auth.repository import AuthRepository

    assert AuthRepository is not None


def test_service_no_db_dependency():
    src = Path("api/features/auth/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
