from unittest.mock import MagicMock

from seed_test_users import seed_users


def test_seed_users_creates_one_user_per_role_and_prints_new_passwords():
    cur = MagicMock()
    # per user: SELECT id (miss) -> INSERT ... RETURNING id -> SELECT password_hash (miss, so a new one gets set)
    cur.fetchone.side_effect = [
        None, (1,), None,  # hr_staff_test: created, no password yet
        None, (2,), None,  # engineer_test: created, no password yet
        None, (3,), None,  # executive_test: created, no password yet
    ]
    role_id_map = {"hr_staff": 10, "engineer": 20, "executive": 30}

    results = seed_users(cur, role_id_map)

    assert [r["role"] for r in results] == ["hr_staff", "engineer", "executive"]
    assert [r["user_id"] for r in results] == [1, 2, 3]
    assert all(r["created"] for r in results)
    # each result names the exact .env var the printed password belongs in
    assert [r["password_env_var"] for r in results] == [
        "TEST_HR_STAFF_PASSWORD", "TEST_ENGINEER_PASSWORD", "TEST_EXECUTIVE_PASSWORD",
    ]
    # every new user gets a freshly generated, printable plaintext password
    for r in results:
        assert isinstance(r["plaintext_password"], str)
        assert len(r["plaintext_password"]) > 0


def test_seed_users_reuses_existing_ids_idempotently_and_leaves_passwords_alone():
    cur = MagicMock()
    # per user: SELECT id (hit, existing) -> SELECT password_hash (hit, already set)
    cur.fetchone.side_effect = [
        (1,), ("$2b$12$existinghash1",),
        (2,), ("$2b$12$existinghash2",),
        (3,), ("$2b$12$existinghash3",),
    ]
    role_id_map = {"hr_staff": 10, "engineer": 20, "executive": 30}

    results = seed_users(cur, role_id_map)

    assert [r["user_id"] for r in results] == [1, 2, 3]
    assert all(not r["created"] for r in results)
    # no password change, nothing to print, for users that already have a hash
    assert all(r["plaintext_password"] is None for r in results)
    # only the SELECTs -- no INSERT, no password UPDATE
    assert cur.execute.call_count == 6


def test_seed_users_backfills_password_for_existing_user_with_no_hash_yet():
    cur = MagicMock()
    # first user: exists but predates password auth (no hash yet) -> gets one now
    # remaining users: exist and already have a hash -> untouched
    cur.fetchone.side_effect = [
        (1,), None,
        (2,), ("$2b$12$existinghash2",),
        (3,), ("$2b$12$existinghash3",),
    ]
    role_id_map = {"hr_staff": 10, "engineer": 20, "executive": 30}

    results = seed_users(cur, role_id_map)

    hr_result = results[0]
    assert hr_result["created"] is False
    assert isinstance(hr_result["plaintext_password"], str)
    assert results[1]["plaintext_password"] is None
    assert results[2]["plaintext_password"] is None
