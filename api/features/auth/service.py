from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from api.features.auth.models import AuthToken
from api.features.auth.ports import ICredentialStore

_SECRET_KEY = os.getenv("JWT_SECRET", "triplea-dev-secret-change-in-production")
_ALGORITHM = "HS256"
_EXPIRE_MINUTES = 60 * 24


class AuthService:
    def __init__(self, credentials: ICredentialStore) -> None:
        self._credentials = credentials

    def authenticate(self, username: str, password: str) -> AuthToken | None:
        if not self._credentials.verify(username, password):
            return None
        return AuthToken(access_token=self._create_token(username))

    def _create_token(self, subject: str) -> str:
        try:
            from jose import jwt

            expire = datetime.now(timezone.utc) + timedelta(minutes=_EXPIRE_MINUTES)
            return jwt.encode(
                {"sub": subject, "exp": expire},
                _SECRET_KEY,
                algorithm=_ALGORITHM,
            )
        except ImportError:
            return "demo-token"
