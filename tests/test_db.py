from unittest.mock import MagicMock, call

from ingestion.db import (
    delete_document_if_exists,
    get_or_create_user,
    get_password_hash,
    get_role_id_map,
    get_user_by_email,
    insert_chunks,
    insert_document,
    insert_document_roles,
    set_password_hash,
)


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
