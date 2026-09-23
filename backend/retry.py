"""Retry with exponential backoff for transient Groq errors inside the
agent loop, capped at a few attempts, falling back to a clean message
rather than propagating a 500. Safe to retry the whole call: conversation
history is only mutated by qa.conversation.run_turn AFTER a successful
run_agent() return, so a failed attempt never leaves partial state behind
for the next retry to build on."""

import time

import groq

MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 1.0

FALLBACK_MESSAGE = "I'm temporarily unable to process your request. Please try again in a moment."

RETRYABLE_EXCEPTIONS = (
    groq.RateLimitError,
    groq.APITimeoutError,
    groq.APIConnectionError,
    groq.InternalServerError,
    groq.BadRequestError,  # covers e.g. "failed to parse tool call arguments as JSON"
)


class TransientLLMError(Exception):
    """Raised after MAX_ATTEMPTS retryable failures -- callers should
    catch this and return FALLBACK_MESSAGE instead of a 500."""


def call_with_retry(func, *args, **kwargs):
    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return func(*args, **kwargs)
        except RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(BASE_DELAY_SECONDS * (2**attempt))
    raise TransientLLMError(str(last_exc)) from last_exc
