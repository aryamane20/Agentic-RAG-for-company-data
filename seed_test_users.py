#!/usr/bin/env python3
"""Seed one test user per role, for manually exercising permission-scoped
search. Idempotent on email -- safe to re-run."""

from ingestion import db

TEST_USERS = [
    ("Test HR Staff", "hr_staff_test@example.com", "hr_staff"),
    ("Test Engineer", "engineer_test@example.com", "engineer"),
    ("Test Executive", "executive_test@example.com", "executive"),
]


def seed_users(cur, role_id_map):
    results = []
    for name, email, role_name in TEST_USERS:
        role_id = role_id_map[role_name]
        user_id, created = db.get_or_create_user(cur, name, email, role_id)
        results.append(
            {"user_id": user_id, "name": name, "email": email, "role": role_name, "created": created}
        )
    return results


def main():
    conn = db.get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                role_id_map = db.get_role_id_map(cur)
                results = seed_users(cur, role_id_map)
    finally:
        conn.close()

    print("Test users:")
    for r in results:
        status = "created" if r["created"] else "already existed"
        print(f"  user_id={r['user_id']:<4} role={r['role']:<10} email={r['email']:<28} ({status})")


if __name__ == "__main__":
    main()
