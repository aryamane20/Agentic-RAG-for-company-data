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
from backend.schemas import ChatRequest, ChatResponse, LoginRequest, LoginResponse
from backend.store import ConversationStore, IdempotencyStore
from ingestion import db, embeddings
from qa import llm as llm_module

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.embed_model = embeddings.load_model()
    app.state.llm = llm_module.get_llm()
    app.state.db_pool = db.get_connection_pool()
    app.state.conversations = ConversationStore()
    app.state.idempotency = IdempotencyStore()
    yield
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


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
def chat(payload: ChatRequest, request: Request):
    # get_current_user() is called manually (not via Depends()) so it
    # runs AFTER @limiter.limit's own check above -- see get_current_user's
    # docstring for why a Depends()-based check would bypass rate limiting
    # for unauthenticated requests entirely.
    user_id, _role = get_current_user(request.headers.get("authorization"))
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    message_id = payload.message_id or str(uuid.uuid4())

    if payload.message_id is not None:
        cached = request.app.state.idempotency.get(user_id, payload.message_id)
        if cached is not None:
            return JSONResponse(content=cached)

    state = request.app.state.conversations.get_or_create(user_id, conversation_id)

    conn = db.get_pooled_connection(request.app.state.db_pool)
    try:
        with conn.cursor() as cur:
            try:
                answer, hit_cap, search_log, _new_summary, _blocked_reason, _pii_findings = (
                    retry.call_with_retry(
                        ask_once,
                        cur,
                        request.app.state.embed_model,
                        request.app.state.llm,
                        state,
                        payload.message,
                        user_id,
                    )
                )
            except retry.TransientLLMError:
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
    finally:
        conn.rollback()
        request.app.state.db_pool.putconn(conn)

    source_documents = sorted(
        {chunk["filename"] for entry in search_log for chunk in entry["chunks"]}
    )

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
