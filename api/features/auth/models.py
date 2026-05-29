from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthCredentials:
    username: str
    password: str


@dataclass(frozen=True)
class AuthToken:
    access_token: str
    token_type: str = "bearer"
