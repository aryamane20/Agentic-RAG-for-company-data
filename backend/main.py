"""FastAPI app wrapping the existing RAG pipeline: /login issues JWTs,
/chat runs the agentic loop (guardrails, RBAC-scoped retrieval) behind
auth, reusing ask.ask_once so there's one code path for both the CLI and
the API. Run from the repo root: uvicorn backend.main:app --reload"""

import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ask import ask_once
from backend import auth, retry
from backend.errors import RequestIDMiddleware, register_error_handlers
from backend.ratelimit import LOGIN_RATE_LIMIT, RATE_LIMIT, limiter
from backend.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationSummary,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageOut,
)
from backend.store import ConversationStore, IdempotencyStore
from ingestion import db, embeddings
from qa import llm as llm_module
from qa.tracing import build_langfuse_client

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.embed_model = embeddings.load_model()
    app.state.llm = llm_module.get_llm()
    app.state.db_pool = db.get_connection_pool()
    app.state.conversations = ConversationStore()
    app.state.idempotency = IdempotencyStore()
    # Built once at startup, not per-request -- the client batches and
    # flushes traces on a background thread, so per-request construction
    # would both be wasteful and drop that batching. None if LANGFUSE_*
    # isn't set, which every call site below treats as "tracing is off."
    app.state.langfuse = build_langfuse_client()
    yield
    if app.state.langfuse is not None:
        app.state.langfuse.flush()
    app.state.db_pool.closeall()


app = FastAPI(title="RAG Chat API", lifespan=lifespan)

# Only the Next.js frontend's own origin may call this API directly from a
# browser -- not a wildcard. Note this is defense-in-depth, not the main
# access control: the intended path is the Next.js route handlers calling
# this API server-to-server (no browser involved, so CORS doesn't apply to
# that hop at all). RBAC + JWT verification are what actually enforce
# access; CORS just stops some other page's script from hitting this API
# directly from a browser using a signed-in user's cookie/token.
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.state.limiter = limiter
# NOTE: deliberately NOT using SlowAPIMiddleware -- it runs its own
# request-limit check first (with no route-specific limits attached) and
# marks the request as "rate limiting already handled," which causes the
# @limiter.limit(...) decorator below (the one that actually enforces our
# per-user 20/minute rule) to skip itself entirely. The middleware is for
# global default limits; per-route decorators check themselves and don't
# need it -- combining both silently disables the per-route limit.
app.add_middleware(RequestIDMiddleware)
register_error_handlers(app)


@app.get("/health")
def health():
    # Liveness only -- confirms the process is up and serving requests,
    # not that the DB/LLM are reachable. No auth, no rate limit: this is
    # meant to be hit frequently and cheaply by Railway's health checker,
    # not a real API route.
    return {"status": "ok"}


def get_current_user(authorization):
    """The only source of user_id/role for a /chat request -- never the
    request body. Raises 401 for anything wrong with the token, without
    distinguishing missing/malformed/expired in the response.

    Deliberately NOT a FastAPI Depends() -- FastAPI resolves dependencies
    (and any HTTPException they raise) BEFORE calling into the route
    function's body, which is what @limiter.limit's rate-limit check runs
    inside of. A Depends()-based auth check would let unauthenticated
    requests raise 401 before the rate limiter ever sees them, making
    /chat's rate limit trivially bypassable by omitting the token. Called
    manually inside chat() instead, after the rate limiter has already run."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[len("Bearer "):]
    try:
        return auth.decode_access_token(token)
    except auth.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.post("/login", response_model=LoginResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(payload: LoginRequest, request: Request):
    conn = db.get_pooled_connection(request.app.state.db_pool)
    try:
        with conn.cursor() as cur:
            row = db.get_user_by_email(cur, payload.email)
    finally:
        conn.rollback()
        request.app.state.db_pool.putconn(conn)

    invalid_credentials = HTTPException(status_code=401, detail="Invalid email or password")
    if row is None:
        raise invalid_credentials

    user_id, _name, role_name, password_hash = row
    if not auth.verify_password(payload.password, password_hash):
        raise invalid_credentials

    token = auth.create_access_token(user_id, role_name)
    # slowapi's rate-limit decorator (with headers_enabled=True) injects
    # headers onto the raw return value BEFORE FastAPI converts it to a
    # real Response -- it crashes on a bare Pydantic model, so this (and
    # every path in chat() below) returns an explicit JSONResponse instead.
    return JSONResponse(content=LoginResponse(access_token=token).model_dump())


def _call_ask_once(request, cur, state, message, user_id, role, conversation_id):
    """retry.call_with_retry(ask_once, ...), optionally wrapped in a
    Langfuse trace -- one trace per /chat request, tagged with the user's
    role and grouped by conversation_id so a multi-turn conversation shows
    as one session in the Langfuse UI. No-op passthrough when tracing is
    off (app.state.langfuse is None)."""
    langfuse_client = request.app.state.langfuse
    if langfuse_client is None:
        return retry.call_with_retry(
            ask_once, cur, request.app.state.embed_model, request.app.state.llm, state, message, user_id,
        )

    from langfuse.langchain import CallbackHandler

    with langfuse_client.start_as_current_span(
        name="chat", metadata={"conversation_id": conversation_id},
    ):
        langfuse_client.update_current_trace(
            user_id=str(user_id), session_id=conversation_id, tags=[role],
        )
        handler = CallbackHandler()
        return retry.call_with_retry(
            ask_once,
            cur,
            request.app.state.embed_model,
            request.app.state.llm,
            state,
            message,
            user_id,
            config={"callbacks": [handler]},
        )


def _persist_turn(cur, conversation_id, user_id, question, answer, source_documents):
    """Writes both sides of this turn as one unit -- called right before
    the commit at the end of chat(), success or fallback path alike, so
    reloaded history never shows a question with no visible reply. Skips
    the write entirely (rather than raising) if upsert_conversation's
    ownership guard trips -- see its docstring; that guard already
    happened once, fast, at the top of chat(), so this is defense in
    depth against a race, not the primary check."""
    title = db.make_conversation_title(question)
    if not db.upsert_conversation(cur, conversation_id, user_id, title):
        return
    db.insert_message(cur, conversation_id, "user", question, [])
    db.insert_message(cur, conversation_id, "assistant", answer, source_documents)


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
def chat(payload: ChatRequest, request: Request):
    # get_current_user() is called manually (not via Depends()) so it
    # runs AFTER @limiter.limit's own check above -- see get_current_user's
    # docstring for why a Depends()-based check would bypass rate limiting
    # for unauthenticated requests entirely.
    user_id, role = get_current_user(request.headers.get("authorization"))
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    message_id = payload.message_id or str(uuid.uuid4())

    if payload.conversation_id is not None:
        try:
            uuid.UUID(payload.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="conversation_id must be a UUID")

    if payload.message_id is not None:
        cached = request.app.state.idempotency.get(user_id, payload.message_id)
        if cached is not None:
            return JSONResponse(content=cached)

    conn = db.get_pooled_connection(request.app.state.db_pool)
    try:
        try:
            with conn.cursor() as cur:
                # Fail fast (before spending an LLM call) if the client
                # supplied a conversation_id that already belongs to someone
                # else -- upsert_conversation would refuse to persist under
                # it anyway.
                existing_owner = db.get_conversation_owner(cur, conversation_id)
                if existing_owner is not None and existing_owner != user_id:
                    raise HTTPException(status_code=403, detail="This conversation does not belong to you")

                state = request.app.state.conversations.get_or_create(
                    user_id,
                    conversation_id,
                    loader=lambda: [
                        (row[0], row[1])
                        for row in db.get_conversation_messages(cur, conversation_id, user_id)
                    ],
                )

                try:
                    answer, hit_cap, search_log, _new_summary, _blocked_reason, _pii_findings = (
                        _call_ask_once(request, cur, state, payload.message, user_id, role, conversation_id)
                    )
                except retry.TransientLLMError:
                    _persist_turn(cur, conversation_id, user_id, payload.message, retry.FALLBACK_MESSAGE, [])
                    conn.commit()
                    response_dict = ChatResponse(
                        answer=retry.FALLBACK_MESSAGE,
                        source_documents=[],
                        conversation_id=conversation_id,
                        message_id=message_id,
                        hit_cap=False,
                    ).model_dump()
                    if payload.message_id is not None:
                        request.app.state.idempotency.set(user_id, payload.message_id, response_dict)
                    return JSONResponse(content=response_dict)

                source_documents = sorted(
                    {chunk["filename"] for entry in search_log for chunk in entry["chunks"]}
                )
                _persist_turn(cur, conversation_id, user_id, payload.message, answer, source_documents)
            conn.commit()
        except Exception:
            # Every path above that succeeds already committed and
            # returned; reaching here means something raised (the 403
            # above, a search/LLM error, anything) with the transaction
            # still open. Roll back before the connection goes back to the
            # pool -- otherwise the next request to borrow it inherits an
            # aborted transaction and every query on it fails.
            conn.rollback()
            raise
    finally:
        request.app.state.db_pool.putconn(conn)

    response_dict = ChatResponse(
        answer=answer,
        source_documents=source_documents,
        conversation_id=conversation_id,
        message_id=message_id,
        hit_cap=hit_cap,
    ).model_dump()

    if payload.message_id is not None:
        request.app.state.idempotency.set(user_id, payload.message_id, response_dict)

    return JSONResponse(content=response_dict)


@app.get("/me", response_model=MeResponse)
@limiter.limit(RATE_LIMIT)
def me(request: Request):
    # Same manual (non-Depends) auth check as chat() -- see get_current_user's
    # docstring. Display-only data (name/email/role for the sidebar badge);
    # authorization elsewhere always comes from the JWT's role claim, never
    # from this lookup.
    user_id, _role = get_current_user(request.headers.get("authorization"))

    conn = db.get_pooled_connection(request.app.state.db_pool)
    try:
        with conn.cursor() as cur:
            row = db.get_user_by_id(cur, user_id)
    finally:
        conn.rollback()
        request.app.state.db_pool.putconn(conn)

    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    name, email, role_name = row
    return JSONResponse(content=MeResponse(name=name, email=email, role=role_name).model_dump())


@app.get("/conversations")
@limiter.limit(RATE_LIMIT)
def list_conversations(request: Request):
    user_id, _role = get_current_user(request.headers.get("authorization"))

    conn = db.get_pooled_connection(request.app.state.db_pool)
    try:
        with conn.cursor() as cur:
            rows = db.list_conversations(cur, user_id)
    finally:
        conn.rollback()
        request.app.state.db_pool.putconn(conn)

    summaries = [
        ConversationSummary(id=str(conv_id), title=title, updated_at=updated_at).model_dump(mode="json")
        for conv_id, title, updated_at in rows
    ]
    return JSONResponse(content=summaries)


@app.get("/conversations/{conversation_id}")
@limiter.limit(RATE_LIMIT)
def get_conversation(conversation_id: str, request: Request):
    user_id, _role = get_current_user(request.headers.get("authorization"))

    try:
        uuid.UUID(conversation_id)
    except ValueError:
        # Not a well-formed UUID at all -- can't match any row, so treat
        # it as not-found rather than letting an invalid-input-syntax
        # error reach Postgres and surface as a 500.
        raise HTTPException(status_code=404, detail="Conversation not found")

    conn = db.get_pooled_connection(request.app.state.db_pool)
    try:
        with conn.cursor() as cur:
            if not db.conversation_belongs_to_user(cur, conversation_id, user_id):
                raise HTTPException(status_code=404, detail="Conversation not found")
            rows = db.get_conversation_messages(cur, conversation_id, user_id)
    finally:
        conn.rollback()
        request.app.state.db_pool.putconn(conn)

    messages = [
        MessageOut(
            role=role, content=content, source_documents=source_documents or [], created_at=created_at,
        ).model_dump(mode="json")
        for role, content, source_documents, created_at in rows
    ]
    return JSONResponse(content=messages)
