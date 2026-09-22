"""The search_documents tool: wraps qa.retrieval so the agent can call it
during its reasoning loop. Distance scores are recorded for debugging but
deliberately withheld from the model -- it has no reliable basis to
interpret a raw cosine distance number."""

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from qa import retrieval


class SearchDocumentsInput(BaseModel):
    query: str = Field(
        description=(
            "A natural language search query describing what information you "
            "need. Rephrase or narrow the query on repeated calls if earlier "
            "results were insufficient."
        )
    )


def format_chunks_for_model(chunks):
    """Render retrieved chunks as a plain string for the model to read,
    each tagged with its source filename. No distance scores included."""
    if not chunks:
        return "No matching results found."

    blocks = [f"[Source: {c['filename']}]\n{c['content']}" for c in chunks]
    return "\n\n---\n\n".join(blocks)


def build_search_tool(cur, embed_model, user_id, top_k=retrieval.DEFAULT_TOP_K, on_search=None):
    """Build the search_documents tool bound to a live cursor, embedding
    model, and a fixed user_id. user_id is bound here, at tool-build time,
    from a value the caller controls -- it is NOT part of the tool's args
    schema, so the model never sees it, passes it, or can override it.
    `on_search`, if given, is called with (query, chunks) after every
    search -- used to record the full trace for debug_output."""

    def _search(query: str) -> str:
        vector = retrieval.embed_question(embed_model, query)
        chunks = retrieval.search_chunks(cur, vector, user_id=user_id, top_k=top_k)
        if on_search is not None:
            on_search(query, chunks)
        return format_chunks_for_model(chunks)

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
