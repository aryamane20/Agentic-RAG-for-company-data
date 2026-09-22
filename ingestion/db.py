"""Database writes: documents -> document_roles -> chunks, per document,
each wrapped in one transaction. Delete-and-replace on filename gives
rerun safety (document_roles/chunks cascade-delete automatically)."""

DB_CONFIG = {
    "host": "localhost",
    "port": 5435,
    "dbname": "rag_db",
    "user": "rag_user",
    "password": "rag_password",
}


def get_connection(config=None):
    import psycopg2
    from pgvector.psycopg2 import register_vector

    conn = psycopg2.connect(**(config or DB_CONFIG))
    register_vector(conn)
    return conn


def get_role_id_map(cur):
    """Return {role_name: role_id} for every seeded role."""
    cur.execute("SELECT id, name FROM roles")
    return {name: role_id for role_id, name in cur.fetchall()}


def delete_document_if_exists(cur, filename):
    """Delete a document row by filename, if present. document_roles and
    chunks cascade-delete via their FK. Returns True if a row was deleted."""
    cur.execute("DELETE FROM documents WHERE filename = %s RETURNING id", (filename,))
    return cur.fetchone() is not None


def insert_document(cur, filename, department):
    cur.execute(
        "INSERT INTO documents (filename, department) VALUES (%s, %s) RETURNING id",
        (filename, department),
    )
    return cur.fetchone()[0]


def insert_document_roles(cur, document_id, role_ids):
    # dedup while preserving order -- a policy config typo listing the same
    # role twice (e.g. "allowed_roles": ["engineer", "engineer"]) would
    # otherwise violate document_roles' UNIQUE(document_id, role_id) and
    # fail the whole document's ingestion over what's really just a
    # cosmetic duplicate.
    for role_id in dict.fromkeys(role_ids):
        cur.execute(
            "INSERT INTO document_roles (document_id, role_id) VALUES (%s, %s)",
            (document_id, role_id),
        )


def get_or_create_user(cur, name, email, role_id):
    """Look up a user by email; insert if not present. Returns
    (user_id, created) -- created is False when an existing row was
    reused, so re-running a seed script never creates duplicates."""
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    if row is not None:
        return row[0], False

    cur.execute(
        "INSERT INTO users (name, email, role_id) VALUES (%s, %s, %s) RETURNING id",
        (name, email, role_id),
    )
    return cur.fetchone()[0], True


def insert_chunks(cur, document_id, chunk_texts, embeddings):
    for content, embedding in zip(chunk_texts, embeddings):
        cur.execute(
            "INSERT INTO chunks (document_id, content, embedding) VALUES (%s, %s, %s)",
            (document_id, content, embedding),
        )
