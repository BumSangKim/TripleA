from __future__ import annotations

import os


class AuthRepository:
    def __init__(self) -> None:
        self._username = os.getenv("DEMO_USERNAME", "admin")
        self._password = os.getenv("DEMO_PASSWORD", "triplea123")

    def verify(self, username: str, password: str) -> bool:
        return username == self._username and password == self._password
