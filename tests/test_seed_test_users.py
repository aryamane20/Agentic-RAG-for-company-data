from unittest.mock import MagicMock

from seed_test_users import seed_users


def test_seed_users_creates_one_user_per_role_using_role_id_map():
    cur = MagicMock()
    # SELECT id FROM users WHERE email = ... -> no match each time -> insert
    cur.fetchone.side_effect = [
        None, (1,),  # hr_staff_test lookup miss, then insert returns id 1
        None, (2,),  # engineer_test lookup miss, then insert returns id 2
        None, (3,),  # executive_test lookup miss, then insert returns id 3
    ]
    role_id_map = {"hr_staff": 10, "engineer": 20, "executive": 30}

    results = seed_users(cur, role_id_map)

    assert [r["role"] for r in results] == ["hr_staff", "engineer", "executive"]
    assert [r["user_id"] for r in results] == [1, 2, 3]
    assert all(r["created"] for r in results)


def test_seed_users_reuses_existing_ids_idempotently():
    cur = MagicMock()
    # every email lookup hits immediately -> no inserts
    cur.fetchone.side_effect = [(1,), (2,), (3,)]
    role_id_map = {"hr_staff": 10, "engineer": 20, "executive": 30}

    results = seed_users(cur, role_id_map)

    assert [r["user_id"] for r in results] == [1, 2, 3]
    assert all(not r["created"] for r in results)
    # only 3 SELECTs, no INSERTs
    assert cur.execute.call_count == 3
