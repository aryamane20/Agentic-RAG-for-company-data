"""Database writes: documents -> document_roles -> chunks, per document,
each wrapped in one transaction. Delete-and-replace on filename gives
rerun safety (document_roles/chunks cascade-delete automatically)."""

import os

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5435")),
    "dbname": os.environ.get("DB_NAME", "rag_db"),
    "user": os.environ.get("DB_USER", "rag_user"),
    "password": os.environ.get("DB_PASSWORD", "rag_password"),
}


def get_connection(config=None):
    import psycopg2
    from pgvector.psycopg2 import register_vector

    conn = psycopg2.connect(**(config or DB_CONFIG))
    register_vector(conn)
    return conn


def get_connection_pool(minconn=1, maxconn=10, config=None):
    """A small pool for the API server -- creating a fresh psycopg2
    connection per HTTP request would be wasteful under real traffic."""
    from psycopg2 import pool as pg_pool

    return pg_pool.SimpleConnectionPool(minconn, maxconn, **(config or DB_CONFIG))


def get_pooled_connection(conn_pool):
    """pgvector's register_vector registers types per-connection, so it
    has to be (re-)applied to whatever connection the pool hands back."""
    from pgvector.psycopg2 import register_vector

    conn = conn_pool.getconn()
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


def get_password_hash(cur, user_id):
    cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    return row[0] if row else None


def set_password_hash(cur, user_id, password_hash):
    cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))


def get_user_by_email(cur, email):
    """Return (user_id, name, role_name, password_hash) for login, or
    None if no user has that email. Joins roles so the caller gets the
    role fresh from the DB, never from client input."""
    cur.execute(
        """
        SELECT u.id, u.name, r.name, u.password_hash
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.email = %s
        """,
        (email,),
    )
    return cur.fetchone()


def get_user_by_id(cur, user_id):
    """Return (name, email, role_name) for display purposes (e.g. the /me
    endpoint) -- never used for authorization, which relies solely on the
    JWT's own role claim."""
    cur.execute(
        """
        SELECT u.name, u.email, r.name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s
        """,
        (user_id,),
    )
    return cur.fetchone()


TITLE_MAX_LENGTH = 48


def make_conversation_title(first_message):
    """Same truncation convention the frontend used for its (now-retired)
    client-only title generation -- kept here so a title generated once,
    server-side, looks identical regardless of which client reads it."""
    if len(first_message) > TITLE_MAX_LENGTH:
        return first_message[:TITLE_MAX_LENGTH] + "…"
    return first_message


def upsert_conversation(cur, conversation_id, user_id, title):
    """Create the conversation row on its first turn, or just bump
    updated_at on a later turn -- title is set once, on insert, and never
    overwritten. The ON CONFLICT's WHERE guards against a client supplying
    a conversation_id that already belongs to a different user: the update
    only fires when the existing row's user_id matches, so a collision
    with someone else's id silently writes nothing instead of attaching
    this user's messages to their conversation. Returns True if the row is
    now owned by user_id (created or already theirs), False if blocked by
    that guard -- callers should treat False as an authorization failure."""
    cur.execute(
        """
        INSERT INTO conversations (id, user_id, title)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE
          SET updated_at = now()
          WHERE conversations.user_id = EXCLUDED.user_id
        RETURNING id
        """,
        (conversation_id, user_id, title),
    )
    return cur.fetchone() is not None


def insert_message(cur, conversation_id, role, content, source_documents):
    cur.execute(
        """
        INSERT INTO messages (conversation_id, role, content, source_documents)
        VALUES (%s, %s, %s, %s)
        """,
        (conversation_id, role, content, source_documents),
    )


def list_conversations(cur, user_id):
    """Return (id, title, updated_at) tuples for the user's conversations,
    most recently active first."""
    cur.execute(
        "SELECT id, title, updated_at FROM conversations WHERE user_id = %s ORDER BY updated_at DESC",
        (user_id,),
    )
    return cur.fetchall()


def conversation_belongs_to_user(cur, conversation_id, user_id):
    cur.execute(
        "SELECT 1 FROM conversations WHERE id = %s AND user_id = %s", (conversation_id, user_id)
    )
    return cur.fetchone() is not None


def get_conversation_owner(cur, conversation_id):
    """Returns the owning user_id, or None if the conversation doesn't
    exist yet -- used to fail fast (403) on a client-supplied
    conversation_id that collides with someone else's, before spending an
    LLM call on a request that upsert_conversation would refuse to
    persist anyway."""
    cur.execute("SELECT user_id FROM conversations WHERE id = %s", (conversation_id,))
    row = cur.fetchone()
    return row[0] if row else None


def get_conversation_messages(cur, conversation_id, user_id):
    """Return (role, content, source_documents, created_at) tuples in
    chronological order. Always scoped by user_id via the join -- a
    caller-supplied conversation_id that belongs to a different user (or
    doesn't exist) simply returns an empty list, never someone else's
    messages, whether this is used for a display read or to hydrate the
    in-memory agent state."""
    cur.execute(
        """
        SELECT m.role, m.content, m.source_documents, m.created_at
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE m.conversation_id = %s AND c.user_id = %s
        ORDER BY m.created_at ASC
        """,
        (conversation_id, user_id),
    )
    return cur.fetchall()


def insert_chunks(cur, document_id, chunk_texts, embeddings):
    for content, embedding in zip(chunk_texts, embeddings):
        cur.execute(
            "INSERT INTO chunks (document_id, content, embedding) VALUES (%s, %s, %s)",
            (document_id, content, embedding),
        )
