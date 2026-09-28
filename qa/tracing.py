"""Shared Langfuse client setup, used by both the eval pipeline
(eval/runner.py) and the live API (backend/main.py) so there's one place
that reads LANGFUSE_* and decides whether tracing is on."""

import os


def build_langfuse_client(quiet=False):
    """Returns a connected Langfuse client, or None if credentials aren't
    set. Never raises on missing config -- tracing is optional, and a
    misconfigured Langfuse setup should never take down search/chat."""
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST")

    if not public_key or not secret_key:
        if not quiet:
            print("(Langfuse credentials not set -- running without tracing)")
        return None

    from langfuse import Langfuse

    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)
