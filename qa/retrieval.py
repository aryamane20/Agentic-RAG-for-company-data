"""Embed a question and run a raw cosine-similarity search against the
chunks table, scoped to what the asking user's role is allowed to see.
No vectorstore wrapper -- the SQL is deliberately visible."""

from ingestion.embeddings import embed_texts

DEFAULT_TOP_K = 5

# Permission scoping: a chunk is only eligible if its document has a
# document_roles row matching the asking user's role. An unknown user_id
# makes the subquery return NULL, and `dr.role_id = NULL` is never true in
# SQL -- so an invalid user fails closed (zero results), not open.
SEARCH_QUERY = """
SELECT c.content, d.filename, (c.embedding <=> %s::vector) AS distance
FROM chunks c
JOIN documents d ON d.id = c.document_id
JOIN document_roles dr ON dr.document_id = d.id
WHERE dr.role_id = (SELECT role_id FROM users WHERE id = %s)
ORDER BY distance
LIMIT %s;
"""


def embed_question(model, question):
    """Embed a single question with the same model/path used at ingestion
    time, so the query vector lives in the same space as chunk vectors."""
    return embed_texts(model, [question])[0]


def search_chunks(cur, query_vector, user_id, top_k=DEFAULT_TOP_K):
    """Run the permission-scoped cosine-distance search and return the
    top_k matches as a list of {content, filename, distance} dicts,
    closest first. Only chunks from documents the given user_id's role
    is allowed to see are eligible."""
    cur.execute(SEARCH_QUERY, (query_vector, user_id, top_k))
    rows = cur.fetchall()
    return [
        {"content": content, "filename": filename, "distance": distance}
        for content, filename, distance in rows
    ]
