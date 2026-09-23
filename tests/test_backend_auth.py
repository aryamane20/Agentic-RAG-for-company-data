import bcrypt
import pytest

from backend import auth


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-do-not-use-in-prod")


def test_verify_password_correct():
    hashed = bcrypt.hashpw(b"correct horse", bcrypt.gensalt()).decode()
    assert auth.verify_password("correct horse", hashed) is True


def test_verify_password_incorrect():
    hashed = bcrypt.hashpw(b"correct horse", bcrypt.gensalt()).decode()
    assert auth.verify_password("wrong password", hashed) is False


def test_verify_password_handles_missing_hash():
    assert auth.verify_password("anything", None) is False


def test_create_and_decode_access_token_round_trips():
    token = auth.create_access_token(user_id=7, role="engineer")

    user_id, role = auth.decode_access_token(token)

    assert user_id == 7
    assert role == "engineer"


def test_decode_access_token_rejects_garbage():
    with pytest.raises(auth.InvalidTokenError):
        auth.decode_access_token("not.a.real.token")


def test_decode_access_token_rejects_wrong_secret(monkeypatch):
    token = auth.create_access_token(user_id=1, role="hr_staff")

    monkeypatch.setenv("JWT_SECRET", "a-different-secret")

    with pytest.raises(auth.InvalidTokenError):
        auth.decode_access_token(token)


def test_decode_access_token_rejects_expired_token(monkeypatch):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    expired_payload = {
        "sub": "3",
        "role": "executive",
        "iat": datetime.now(timezone.utc) - timedelta(minutes=60),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=30),
    }
    expired_token = pyjwt.encode(expired_payload, "test-secret-do-not-use-in-prod", algorithm="HS256")

    with pytest.raises(auth.InvalidTokenError):
        auth.decode_access_token(expired_token)


def test_create_access_token_raises_without_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        auth.create_access_token(user_id=1, role="engineer")
