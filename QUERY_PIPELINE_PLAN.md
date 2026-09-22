# Query-Answering Pipeline Plan (Agentic RAG)

## Architecture

This is an agentic pipeline, not fixed-sequence RAG: the model itself decides
whether to search, how many times, with what query, and when it has enough
to answer. What makes it agentic is that decision loop, not the number of
tools available (currently one; more can be added later without changing
the underlying architecture).

Two nested loops:
- **Outer loop** (`ask.py`, human-facing): type a question, get an answer,
  type another. Plain CLI REPL, no intelligence.
- **Inner loop** (the agent): model decides to call `search_documents`
  zero or more times (capped at 3) before producing a final answer.

No permission/role filtering yet — explicitly deferred to a later step.

## 1. Retrieval (`qa/retrieval.py`)

- `embed_question(model, question)` — reuses `ingestion.embeddings`
  (same `all-MiniLM-L6-v2` model and encode path used at ingestion time,
  so query and chunk vectors live in the same space).
- `search_chunks(cur, query_vector, top_k=5)` — raw SQL, not a vectorstore
  wrapper:
  ```sql
  SELECT c.content, d.filename, (c.embedding <=> %s) AS distance
  FROM chunks c
  JOIN documents d ON d.id = c.document_id
  ORDER BY distance
  LIMIT 5;
  ```
  `<=>` is pgvector's cosine distance operator — the only one that matches
  the `vector_cosine_ops` HNSW index built in `schema.sql`. Using `<->`
  (L2) here would silently skip the index and fall back to a sequential
  scan. Query vector passed once, reused via the `distance` alias.
- Returns a list of dicts: `{content, filename, distance}`. Distance is
  kept in this layer for debugging, but is **not** shown to the LLM (see
  tool section below).
- Connection: reuses `ingestion.db.get_connection()` (same credentials,
  same `pgvector` adapter registration).
- Comment left in the query marking exactly where a future
  `JOIN document_roles ... WHERE role_id = %s` permission filter would go.

## 2. Tool (`qa/tools.py`)

One tool, `search_documents`, wrapping the retrieval function above. Built
via a factory closure so it has access to the live DB cursor and embedding
model without global state:

```python
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

class SearchDocumentsInput(BaseModel):
    query: str = Field(
        description=(
            "A natural language search query describing what information you "
            "need. Rephrase or narrow the query on repeated calls if earlier "
            "results were insufficient."
        )
    )

def build_search_tool(cur, embed_model, top_k=5):
    def _search(query: str) -> str:
        vector = retrieval.embed_question(embed_model, query)
        results = retrieval.search_chunks(cur, vector, top_k=top_k)
        return format_chunks_for_model(results)  # filename + content, no distance

    return StructuredTool.from_function(
        func=_search,
        name="search_documents",
        description=(
            "Searches the internal company document corpus (HR, Engineering, "
            "and Finance policies, guides, and records) and returns the top 5 "
            "most relevant excerpts, each labeled with its source filename."
        ),
        args_schema=SearchDocumentsInput,
    )
```

Deliberate design choice: the tool description states **only what the tool
does** (what it searches, what it returns). All behavioral/looping rules
(must call before answering, may re-query up to 3 times, never use own
knowledge) live solely in the system prompt — keeping one source of truth
per rule instead of duplicating instructions across the tool description
and the system prompt where they could drift out of sync.

Tool result string omits the cosine distance — the model has no reliable
basis to interpret a raw distance number, and showing it risks the model
treating small numeric gaps as meaningful signal. Distance is still
recorded in the debug trace (see below), just not sent to the model.

## 3. System prompt (`qa/prompt.py`)

```
You are a helpful assistant that answers questions using ONLY information
found by searching the internal document corpus with the search_documents
tool. You must call this tool before answering — never answer from your own
knowledge. You may call it more than once with a different or refined query
if the first search doesn't sufficiently answer the question, up to a
maximum of 3 searches.

Do not use any outside knowledge, and do not fill gaps with assumptions or
general knowledge, even if you're confident it's correct. Every claim in
your answer must be traceable to the search results, and you must name
which document (by filename) each piece of information came from.

If the search results are empty, irrelevant, or only partially answer the
question — even after multiple searches — say so explicitly and describe
what's missing, rather than guessing or inferring beyond what was found. It
is always better to say "I don't know based on the provided documents" than
to produce an answer not directly supported by the search results.
```

Initial message list: `[SystemMessage(above), HumanMessage(question)]` —
no pre-fetched context stuffed in up front; context arrives dynamically via
tool-call results during the loop.

## 4. Agent loop (`qa/llm.py`)

- `ChatGroq`, model `llama-3.3-70b-versatile` (overridable via `GROQ_MODEL`
  env var), `temperature=0.0` for deterministic, grounded output.
- `GROQ_API_KEY` read from env; fail fast with a clear error if missing.
- `llm.bind_tools([search_documents])`.
- Loop, capped at **3 tool calls**:
  1. Invoke the model with the current message list.
  2. If the response includes tool calls: execute each via the tool,
     append the results as tool messages, go to 1.
  3. If the response is plain text (no tool calls): that's the final
     answer, loop ends.
- If the cap is hit without a final answer: force one last call with
  tools disabled and an explicit "answer now using only what you've found
  so far" instruction, rather than looping forever.
- Designed to accept the LLM and tool as arguments (dependency injection),
  so the loop is testable with a fake LLM returning canned
  tool-call / no-tool-call responses — no real API calls in unit tests.

## 5. CLI loop (`ask.py`, project root)

- Loads the embedding model, DB connection, and `ChatGroq` LLM once at
  startup.
- `while True:` — prompt for a question, run the agent loop, print the
  retrieved-chunks trace and the final answer as clearly separate
  sections, loop back for the next question.
- Mirrors `ingest.py`'s role as the single orchestration entrypoint that
  knows the end-to-end order; individual modules (`retrieval.py`,
  `tools.py`, `prompt.py`, `llm.py`) stay independently testable and
  unaware of each other.

## 6. Debug trace (`debug_output/queries/`)

Extends the same debug pattern used for ingestion. One JSON file per
question, containing:
- the question and a timestamp
- every search the model issued during the loop (query text, retrieved
  chunks with filename + content + distance, iteration number)
- the final answer
- whether the iteration cap was hit

This is what makes it possible to see *why* the model did or didn't
re-query, not just what it answered.

## Explicitly deferred

- No role/permission filtering in retrieval yet — will be added as a
  `JOIN document_roles` clause at the point already marked in the SQL
  query, once retrieval quality is validated.
- No multi-tool expansion yet (e.g. a second data source, a
  query-reformulation tool) — architecture supports adding tools later
  without restructuring the loop.
