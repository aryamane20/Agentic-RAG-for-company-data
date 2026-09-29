from unittest.mock import MagicMock, call

from ingestion.db import (
    _connection_kwargs,
    conversation_belongs_to_user,
    delete_document_if_exists,
    get_conversation_messages,
    get_conversation_owner,
    get_or_create_user,
    get_password_hash,
    get_role_id_map,
    get_user_by_email,
    get_user_by_id,
    insert_chunks,
    insert_document,
    insert_document_roles,
    insert_message,
    list_conversations,
    make_conversation_title,
    set_password_hash,
    upsert_conversation,
)


def test_connection_kwargs_uses_database_url_when_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@railway-host:5432/railway")

    assert _connection_kwargs() == {"dsn": "postgres://u:p@railway-host:5432/railway"}


def test_connection_kwargs_falls_back_to_discrete_vars_when_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "somehost")
    monkeypatch.setenv("DB_PORT", "5555")
    monkeypatch.setenv("DB_NAME", "somedb")
    monkeypatch.setenv("DB_USER", "someuser")
    monkeypatch.setenv("DB_PASSWORD", "somepass")

    assert _connection_kwargs() == {
        "host": "somehost",
        "port": 5555,
        "dbname": "somedb",
        "user": "someuser",
        "password": "somepass",
    }


def test_get_role_id_map_builds_name_to_id_dict():
    cur = MagicMock()
    cur.fetchall.return_value = [(1, "hr_staff"), (2, "engineer"), (3, "executive")]

    result = get_role_id_map(cur)

    assert result == {"hr_staff": 1, "engineer": 2, "executive": 3}


def test_delete_document_if_exists_returns_true_when_row_deleted():
    cur = MagicMock()
    cur.fetchone.return_value = (5,)

    deleted = delete_document_if_exists(cur, "benefits_guide.md")

    cur.execute.assert_called_once_with(
        "DELETE FROM documents WHERE filename = %s RETURNING id",
        ("benefits_guide.md",),
    )
    assert deleted is True


def test_delete_document_if_exists_returns_false_when_no_row():
    cur = MagicMock()
    cur.fetchone.return_value = None

    deleted = delete_document_if_exists(cur, "new_doc.md")

    assert deleted is False


def test_insert_document_returns_new_id():
    cur = MagicMock()
    cur.fetchone.return_value = (42,)

    doc_id = insert_document(cur, "benefits_guide.md", "hr")

    cur.execute.assert_called_once_with(
        "INSERT INTO documents (filename, department) VALUES (%s, %s) RETURNING id",
        ("benefits_guide.md", "hr"),
    )
    assert doc_id == 42


def test_insert_document_roles_inserts_one_row_per_role():
    cur = MagicMock()

    insert_document_roles(cur, document_id=7, role_ids=[1, 3])

    assert cur.execute.call_count == 2
    cur.execute.assert_has_calls(
        [
            call(
                "INSERT INTO document_roles (document_id, role_id) VALUES (%s, %s)",
                (7, 1),
            ),
            call(
                "INSERT INTO document_roles (document_id, role_id) VALUES (%s, %s)",
                (7, 3),
            ),
        ]
    )


def test_insert_document_roles_dedups_repeated_role_ids():
    cur = MagicMock()

    insert_document_roles(cur, document_id=7, role_ids=[1, 3, 1, 3, 3])

    # only one INSERT per distinct role, even with a policy-config typo
    # listing the same role multiple times
    assert cur.execute.call_count == 2
    cur.execute.assert_has_calls(
        [
            call("INSERT INTO document_roles (document_id, role_id) VALUES (%s, %s)", (7, 1)),
            call("INSERT INTO document_roles (document_id, role_id) VALUES (%s, %s)", (7, 3)),
        ]
    )


def test_get_or_create_user_returns_existing_id_without_inserting():
    cur = MagicMock()
    cur.fetchone.return_value = (7,)

    user_id, created = get_or_create_user(cur, "Test Engineer", "eng@example.com", role_id=2)

    cur.execute.assert_called_once_with(
        "SELECT id FROM users WHERE email = %s", ("eng@example.com",)
    )
    assert user_id == 7
    assert created is False


def test_get_or_create_user_inserts_when_not_found():
    cur = MagicMock()
    cur.fetchone.side_effect = [None, (11,)]

    user_id, created = get_or_create_user(cur, "Test Engineer", "eng@example.com", role_id=2)

    assert cur.execute.call_count == 2
    insert_call = cur.execute.call_args_list[1]
    assert insert_call == call(
        "INSERT INTO users (name, email, role_id) VALUES (%s, %s, %s) RETURNING id",
        ("Test Engineer", "eng@example.com", 2),
    )
    assert user_id == 11
    assert created is True


def test_get_password_hash_returns_hash_when_present():
    cur = MagicMock()
    cur.fetchone.return_value = ("$2b$12$hashedvalue",)

    result = get_password_hash(cur, user_id=1)

    cur.execute.assert_called_once_with("SELECT password_hash FROM users WHERE id = %s", (1,))
    assert result == "$2b$12$hashedvalue"


def test_get_password_hash_returns_none_when_user_missing():
    cur = MagicMock()
    cur.fetchone.return_value = None

    assert get_password_hash(cur, user_id=999) is None


def test_set_password_hash_updates_the_row():
    cur = MagicMock()

    set_password_hash(cur, user_id=1, password_hash="$2b$12$newhash")

    cur.execute.assert_called_once_with(
        "UPDATE users SET password_hash = %s WHERE id = %s", ("$2b$12$newhash", 1)
    )


def test_get_user_by_email_returns_id_name_role_and_hash():
    cur = MagicMock()
    cur.fetchone.return_value = (2, "Test Engineer", "engineer", "$2b$12$hash")

    result = get_user_by_email(cur, "eng@example.com")

    assert result == (2, "Test Engineer", "engineer", "$2b$12$hash")
    executed_sql, params = cur.execute.call_args[0]
    assert "JOIN roles" in executed_sql
    assert params == ("eng@example.com",)


def test_get_user_by_email_returns_none_when_not_found():
    cur = MagicMock()
    cur.fetchone.return_value = None

    assert get_user_by_email(cur, "nobody@example.com") is None


def test_get_user_by_id_returns_name_email_and_role():
    cur = MagicMock()
    cur.fetchone.return_value = ("Test Engineer", "eng@example.com", "engineer")

    result = get_user_by_id(cur, 2)

    assert result == ("Test Engineer", "eng@example.com", "engineer")
    executed_sql, params = cur.execute.call_args[0]
    assert "JOIN roles" in executed_sql
    assert params == (2,)


def test_get_user_by_id_returns_none_when_not_found():
    cur = MagicMock()
    cur.fetchone.return_value = None

    assert get_user_by_id(cur, 999) is None


def test_make_conversation_title_returns_short_message_unchanged():
    assert make_conversation_title("What's the PTO policy?") == "What's the PTO policy?"


def test_make_conversation_title_truncates_long_message():
    long_message = "a" * 60

    title = make_conversation_title(long_message)

    assert title == "a" * 48 + "…"
    assert len(title) == 49


def test_upsert_conversation_returns_true_when_row_written():
    cur = MagicMock()
    cur.fetchone.return_value = ("conv-1",)

    result = upsert_conversation(cur, "conv-1", user_id=1, title="What's the PTO policy?")

    assert result is True
    executed_sql, params = cur.execute.call_args[0]
    assert "ON CONFLICT" in executed_sql
    assert params == ("conv-1", 1, "What's the PTO policy?")


def test_upsert_conversation_returns_false_when_owned_by_another_user():
    # the ON CONFLICT ... WHERE guard returns no row when the existing
    # conversation belongs to a different user_id -- RETURNING then
    # yields nothing, which fetchone() surfaces as None
    cur = MagicMock()
    cur.fetchone.return_value = None

    result = upsert_conversation(cur, "conv-1", user_id=2, title="hijack attempt")

    assert result is False


def test_insert_message_writes_role_content_and_sources():
    cur = MagicMock()

    insert_message(cur, "conv-1", "assistant", "18 days a year.", ["employee_handbook.md"])

    executed_sql, params = cur.execute.call_args[0]
    assert "INSERT INTO messages" in executed_sql
    assert params == ("conv-1", "assistant", "18 days a year.", ["employee_handbook.md"])


def test_list_conversations_returns_rows_as_is():
    cur = MagicMock()
    cur.fetchall.return_value = [("conv-1", "PTO policy", "2026-01-01T00:00:00Z")]

    result = list_conversations(cur, user_id=1)

    assert result == [("conv-1", "PTO policy", "2026-01-01T00:00:00Z")]
    executed_sql, params = cur.execute.call_args[0]
    assert "ORDER BY updated_at DESC" in executed_sql
    assert params == (1,)


def test_conversation_belongs_to_user_true_when_row_found():
    cur = MagicMock()
    cur.fetchone.return_value = (1,)

    assert conversation_belongs_to_user(cur, "conv-1", user_id=1) is True


def test_conversation_belongs_to_user_false_when_no_row():
    cur = MagicMock()
    cur.fetchone.return_value = None

    assert conversation_belongs_to_user(cur, "conv-1", user_id=1) is False


def test_get_conversation_owner_returns_user_id():
    cur = MagicMock()
    cur.fetchone.return_value = (7,)

    assert get_conversation_owner(cur, "conv-1") == 7


def test_get_conversation_owner_returns_none_when_not_found():
    cur = MagicMock()
    cur.fetchone.return_value = None

    assert get_conversation_owner(cur, "conv-1") is None


def test_get_conversation_messages_scopes_by_user_id():
    cur = MagicMock()
    cur.fetchall.return_value = [("user", "hi", [], "2026-01-01T00:00:00Z")]

    result = get_conversation_messages(cur, "conv-1", user_id=1)

    assert result == [("user", "hi", [], "2026-01-01T00:00:00Z")]
    executed_sql, params = cur.execute.call_args[0]
    assert "c.user_id" in executed_sql
    assert params == ("conv-1", 1)


def test_insert_chunks_inserts_one_row_per_chunk_with_matching_embedding():
    cur = MagicMock()
    texts = ["## A\n\nbody a", "## B\n\nbody b"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]

    insert_chunks(cur, document_id=9, chunk_texts=texts, embeddings=embeddings)

    assert cur.execute.call_count == 2
    cur.execute.assert_has_calls(
        [
            call(
                "INSERT INTO chunks (document_id, content, embedding) VALUES (%s, %s, %s)",
                (9, texts[0], embeddings[0]),
            ),
            call(
                "INSERT INTO chunks (document_id, content, embedding) VALUES (%s, %s, %s)",
                (9, texts[1], embeddings[1]),
            ),
        ]
    )
