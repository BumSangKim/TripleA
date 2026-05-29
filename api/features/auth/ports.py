from __future__ import annotations

from typing import Protocol


class ICredentialStore(Protocol):
    def verify(self, username: str, password: str) -> bool: ...
