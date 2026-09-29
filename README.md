# Solstice Analytics RAG Chat

An internal knowledge assistant for a fictional company, Solstice Analytics. Employees ask questions in plain language and get answers grounded strictly in internal documents (HR, Engineering, Finance), with access enforced per role at the database query level, not just in the UI.

This is a full stack project: a Python ingestion pipeline, an agentic retrieval augmented generation (RAG) backend, and a Next.js frontend, all containerized and deployable to free tier hosting.

## What it does

- A user logs in and asks a question in a chat interface.
- The backend runs an agentic loop: the language model decides whether to search the document corpus, refines its query if the first search is not enough, and stops once it has enough information or hits a search cap.
- Every search is scoped by the user's role at the SQL level. An engineer's query can only ever retrieve chunks from documents that engineer is allowed to see. There is no application level filtering step that could be bypassed.
- If the answer is not grounded in retrieved documents, the assistant refuses with a standardized message rather than guessing.
- Conversations persist to a real database, not browser storage, so chat history survives logout, page reload, and even a server restart.
- Guardrails catch prompt injection attempts (both direct, in the user's message, and indirect, embedded in a retrieved document) and redact PII in model output.

## Architecture

```
hr/, engineering/, finance/     Source documents (markdown)
access_policy.json              Which roles can see which documents
ingest.py                       Chunks docs, embeds them, writes to Postgres
seed_test_users.py              Creates one test user per role

qa/                              Core RAG logic (shared by the CLI and the API)
  retrieval.py                  RBAC-scoped vector search
  tools.py                      The search_documents tool the agent calls
  llm.py                        The agentic tool-calling loop
  conversation.py               Multi-turn memory with LLM-based summarization
  guardrails.py                 Input/output guardrails
  tracing.py                    Optional Langfuse tracing

backend/                        FastAPI application
  main.py                       Routes: /login, /chat, /me, /conversations, /health
  auth.py                       JWT creation and verification
  store.py                      In-memory conversation cache, hydrated from Postgres

frontend/                       Next.js application
  app/login, app/chat           Pages
  app/api/*                     Route handlers that call the backend server side

eval/                            Golden dataset evaluation harness (Ragas based)
tests/                           Unit tests
```

### Retrieval and generation

The system does not do a single fixed retrieval step. The language model is given a `search_documents` tool and decides for itself whether to call it, what to search for, and whether to search again with a refined query, up to a cap of three searches per turn. This is closer to how a careful human researcher would work than a naive "embed the question, fetch top k, answer" pipeline.

Retrieval uses pgvector's HNSW index with cosine distance. Access control is enforced by joining the chunk search against the requesting user's role inside the SQL query itself, so a search simply cannot return a chunk the user is not allowed to see.

### Guardrails

Input guardrails use regex pattern matching to catch direct prompt injection attempts (for example, "ignore your previous instructions"). Output guardrails redact PII patterns from the model's answer before it reaches the user. Retrieved document content is explicitly framed in the system prompt as data to read, never as instructions to follow, which defends against a document itself containing an embedded injection attempt.

### Multi-turn memory

Conversation history is kept as raw messages up to a threshold, then older turns are compressed into a real LLM-generated summary rather than being truncated or dropped. This keeps long conversations within the model's context window while preserving what was actually discussed.

### Persistence

Conversations and messages are stored in Postgres, not in memory or in browser storage. The in-memory cache used during an active request is only a performance optimization: if it is empty for a given conversation (for example, after a server restart), it is transparently rehydrated from the database before the next turn runs, so multi-turn context is never lost.

## Tech stack

- Python 3.11, FastAPI, LangChain, Groq (LLM inference)
- PostgreSQL with the pgvector extension, sentence-transformers (all-MiniLM-L6-v2) for embeddings
- Next.js 16 (App Router), React 19, TypeScript
- Docker and Docker Compose for local orchestration
- Optional: Langfuse for LLM observability, Ragas for automated evaluation

## Running locally

Requires Docker and Docker Compose.

1. Copy `.env.example` to `.env` and fill in `GROQ_API_KEY` and `JWT_SECRET` at minimum. See the comments in `.env.example` for what each variable is for.
2. From the repository root, run:

   ```
   docker compose up --build
   ```

3. On first boot against an empty database, the API container automatically seeds three test users (one per role) and ingests the document corpus. Watch the logs for the generated test passwords, printed once:

   ```
   [bootstrap] users table is empty -- seeding test users
   ...
   password (shown once, not stored anywhere): <password>
   ```

4. The API is available at `http://localhost:8000`. `/health` returns `200` once the service is ready.

To run the frontend locally against this backend, see `frontend/`. It is a separate Next.js application with its own `npm install` and `npm run dev`, configured via `BACKEND_URL` in its own `.env.local`.

## Running tests

```
python -m pytest tests/ -q
```

The suite covers RBAC scoping, guardrails, conversation summarization, the retry and idempotency logic, the persistence layer, and more. It runs without needing a live database or LLM connection; external calls are mocked.

## Deployment

The application is designed to run on any platform that can build from the provided `Dockerfile` and provide a `DATABASE_URL` environment variable. It has been deployed and verified on a free tier stack: Supabase for the database, Render for the API, and Vercel for the frontend. `DATABASE_URL` support, a `/health` endpoint for platform health checks, and a configurable listen port are all already wired in for this reason.

## Test accounts

Three roles are seeded by default: `engineer`, `hr_staff`, and `executive`. Each sees a different slice of the document corpus per `access_policy.json`, which is the intended way to see the RBAC enforcement in action: ask the same question as two different roles and compare the answers.
