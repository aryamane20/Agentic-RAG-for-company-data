from unittest.mock import MagicMock

import pytest

from backend import auth
from backend.ratelimit import rate_limit_key


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-do-not-use-in-prod")


def make_request(auth_header=None, client_host="203.0.113.5"):
    request = MagicMock()
    request.headers = {"authorization": auth_header} if auth_header else {}
    request.client.host = client_host
    return request


def test_rate_limit_key_uses_user_id_from_valid_token():
    token = auth.create_access_token(user_id=42, role="engineer")

    key = rate_limit_key(make_request(auth_header=f"Bearer {token}"))

    assert key == "user:42"


def test_rate_limit_key_falls_back_to_ip_when_no_auth_header():
    key = rate_limit_key(make_request(auth_header=None))

    assert key == "ip:203.0.113.5"


def test_rate_limit_key_falls_back_to_ip_for_invalid_token():
    key = rate_limit_key(make_request(auth_header="Bearer not-a-real-token"))

    assert key == "ip:203.0.113.5"


def test_rate_limit_key_isolates_different_users():
    token1 = auth.create_access_token(user_id=1, role="hr_staff")
    token2 = auth.create_access_token(user_id=2, role="engineer")

    key1 = rate_limit_key(make_request(auth_header=f"Bearer {token1}"))
    key2 = rate_limit_key(make_request(auth_header=f"Bearer {token2}"))

    assert key1 != key2
