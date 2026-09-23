from unittest.mock import MagicMock

import groq
import pytest

from backend.retry import TransientLLMError, call_with_retry


def _make_groq_error(cls):
    """groq's exception classes require a real httpx response/body to
    construct; build the minimum needed for a unit test."""
    import httpx

    request = httpx.Request("POST", "https://api.groq.com/x")
    response = httpx.Response(status_code=429, request=request)
    if cls is groq.APIConnectionError or cls is groq.APITimeoutError:
        return cls(request=request)
    return cls(message="synthetic error", response=response, body=None)


def test_call_with_retry_returns_immediately_on_success():
    func = MagicMock(return_value="ok")

    result = call_with_retry(func, "arg1", kwarg="v")

    assert result == "ok"
    func.assert_called_once_with("arg1", kwarg="v")


def test_call_with_retry_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("backend.retry.time.sleep", lambda _: None)
    error = _make_groq_error(groq.RateLimitError)
    func = MagicMock(side_effect=[error, error, "ok"])

    result = call_with_retry(func)

    assert result == "ok"
    assert func.call_count == 3


def test_call_with_retry_raises_transient_error_after_max_attempts(monkeypatch):
    monkeypatch.setattr("backend.retry.time.sleep", lambda _: None)
    error = _make_groq_error(groq.InternalServerError)
    func = MagicMock(side_effect=[error, error, error])

    with pytest.raises(TransientLLMError):
        call_with_retry(func)

    assert func.call_count == 3


def test_call_with_retry_does_not_catch_non_groq_exceptions():
    func = MagicMock(side_effect=ValueError("not a groq error"))

    with pytest.raises(ValueError):
        call_with_retry(func)

    func.assert_called_once()


def test_call_with_retry_catches_bad_request_error_for_malformed_tool_calls(monkeypatch):
    # this is the exact failure mode observed live: Groq's model
    # occasionally returns malformed JSON for a tool call
    monkeypatch.setattr("backend.retry.time.sleep", lambda _: None)
    error = _make_groq_error(groq.BadRequestError)
    func = MagicMock(side_effect=[error, "recovered"])

    result = call_with_retry(func)

    assert result == "recovered"
