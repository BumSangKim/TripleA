from __future__ import annotations

from api.features.auth.models import AuthCredentials, AuthToken
from api.features.auth.ports import ICredentialStore
from api.features.auth.schemas import TokenResponse


def test_token_response_schema():
    r = TokenResponse(access_token="abc")
    assert r.access_token == "abc"
    assert r.token_type == "bearer"


def test_auth_credentials_model():
    creds = AuthCredentials(username="u", password="p")
    assert creds.username == "u"
    assert creds.password == "p"


def test_auth_token_model():
    token = AuthToken(access_token="tok")
    assert token.access_token == "tok"
    assert token.token_type == "bearer"


def test_icredential_store_protocol_importable():
    assert ICredentialStore is not None


def test_icredential_store_structural_subtype():
    class FakeStore:
        def verify(self, username: str, password: str) -> bool:
            return True

    store: ICredentialStore = FakeStore()
    assert store.verify("u", "p") is True
