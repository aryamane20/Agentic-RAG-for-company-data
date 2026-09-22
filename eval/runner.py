"""Executes each golden-dataset case through the exact same code path
ask.py uses (guardrails -> RBAC-scoped retrieval -> agent loop -> output
redaction), capturing retrieved chunks, final answer, and the
denied/blocked outcome. Handles temporary corpus setup/teardown for
guardrail cases that need a planted adversarial document, and wraps each
case in a Langfuse trace tagged with the run's version label."""

import json
import os
import time

from ask import ask_once
from ingestion import chunking, db, embeddings
from qa import conversation

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(EVAL_DIR, "golden_dataset.json")

MAX_RATE_LIMIT_RETRIES = 5
RATE_LIMIT_BACKOFF_SECONDS = 8


def _is_rate_limit_error(exc):
    # groq.RateLimitError subclasses openai-style APIStatusError with a
    # status_code attribute; match on that (or the message) rather than
    # importing groq's exception class directly, so this stays robust to
    # whichever client library actually raised it (Groq call vs Ragas'
    # internal judge-LLM call use the same underlying groq client).
    status_code = getattr(exc, "status_code", None)
    return status_code == 429 or "rate_limit" in str(exc).lower()


def with_rate_limit_retry(func, *args, **kwargs):
    for attempt in range(MAX_RATE_LIMIT_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if not _is_rate_limit_error(exc) or attempt == MAX_RATE_LIMIT_RETRIES - 1:
                raise
            wait = RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1)
            print(f"  (rate limited, waiting {wait}s before retry {attempt + 1}/{MAX_RATE_LIMIT_RETRIES})")
            time.sleep(wait)


def load_cases(path=DATASET_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["cases"]


def _insert_setup_document(cur, embed_model, setup_doc):
    chunk_texts = chunking.chunk_markdown(setup_doc["content"])
    vectors = embeddings.embed_texts(embed_model, chunk_texts)

    db.delete_document_if_exists(cur, setup_doc["filename"])
    document_id = db.insert_document(cur, setup_doc["filename"], setup_doc["department"])

    role_id_map = db.get_role_id_map(cur)
    role_ids = [role_id_map[r] for r in setup_doc["allowed_roles"]]
    db.insert_document_roles(cur, document_id, role_ids)
    db.insert_chunks(cur, document_id, chunk_texts, vectors)
    cur.connection.commit()


def _remove_setup_document(cur, filename):
    db.delete_document_if_exists(cur, filename)
    cur.connection.commit()


def run_case(cur, embed_model, llm, case, config=None):
    """Run one golden-dataset case. Returns a raw (unscored) result dict.
    `config` (a LangChain RunnableConfig) is forwarded so a Langfuse
    callback handler can be attached by the caller."""
    setup_doc = case.get("setup_document")
    if setup_doc:
        _insert_setup_document(cur, embed_model, setup_doc)

    try:
        state = conversation.start_session()
        start = time.monotonic()
        answer, hit_cap, search_log, new_summary, blocked_reason, pii_findings = ask_once(
            cur, embed_model, llm, state, case["question"], case["user_id"], config=config
        )
        latency_seconds = time.monotonic() - start

        return {
            "case_id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "user_role": case["user_role"],
            "reference_answer": case.get("reference_answer"),
            "answer": answer,
            "hit_cap": hit_cap,
            "blocked_reason": blocked_reason,
            "pii_findings": pii_findings,
            "search_log": search_log,
            "latency_seconds": latency_seconds,
        }
    finally:
        if setup_doc:
            _remove_setup_document(cur, setup_doc["filename"])


def _build_langfuse_client():
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST")

    if not public_key or not secret_key:
        print("(Langfuse credentials not set -- running without tracing)")
        return None

    from langfuse import Langfuse

    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def run_all_cases(cur, embed_model, llm, version_label, cases=None, seconds_between_cases=0):
    """Run every case in the golden dataset, tracing each one to Langfuse
    (if configured) tagged with `version_label`. Returns the list of raw
    result dicts, each carrying its Langfuse trace_id (or None).
    `seconds_between_cases` paces requests to stay under a tokens-per-minute
    limit -- separate from with_rate_limit_retry, which reacts to a 429
    after the fact; this tries to avoid triggering one in the first place."""
    if cases is None:
        cases = load_cases()

    langfuse_client = _build_langfuse_client()
    results = []

    for i, case in enumerate(cases, start=1):
        if i > 1 and seconds_between_cases:
            time.sleep(seconds_between_cases)

        print(f"  [{i}/{len(cases)}] {case['id']}")

        if langfuse_client is None:
            result = with_rate_limit_retry(run_case, cur, embed_model, llm, case)
            result["trace_id"] = None
            results.append(result)
            continue

        from langfuse.langchain import CallbackHandler

        with langfuse_client.start_as_current_span(
            name=case["id"],
            version=version_label,
            metadata={"category": case["category"], "user_role": case["user_role"]},
        ):
            langfuse_client.update_current_trace(tags=[version_label, case["category"]])
            trace_id = langfuse_client.get_current_trace_id()
            handler = CallbackHandler()

            result = with_rate_limit_retry(
                run_case, cur, embed_model, llm, case, config={"callbacks": [handler]}
            )
            result["trace_id"] = trace_id
            results.append(result)

    if langfuse_client is not None:
        langfuse_client.flush()

    return results
