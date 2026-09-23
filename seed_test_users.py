#!/usr/bin/env python3
"""Seed one test user per role, for manually exercising permission-scoped
search and login. Idempotent on email -- safe to re-run. A password is
generated and printed ONCE for any user that doesn't have one yet (new
users, and existing users from before password auth existed); an
already-set password is never regenerated or re-shown, since only its
bcrypt hash is stored."""

import secrets

import bcrypt

from ingestion import db

TEST_USERS = [
    ("Test HR Staff", "hr_staff_test@example.com", "hr_staff", "TEST_HR_STAFF_PASSWORD"),
    ("Test Engineer", "engineer_test@example.com", "engineer", "TEST_ENGINEER_PASSWORD"),
    ("Test Executive", "executive_test@example.com", "executive", "TEST_EXECUTIVE_PASSWORD"),
]


def generate_password():
    return secrets.token_urlsafe(9)


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def seed_users(cur, role_id_map):
    results = []
    for name, email, role_name, password_env_var in TEST_USERS:
        role_id = role_id_map[role_name]
        user_id, created = db.get_or_create_user(cur, name, email, role_id)

        existing_hash = db.get_password_hash(cur, user_id)
        plaintext_password = None
        if existing_hash is None:
            plaintext_password = generate_password()
            db.set_password_hash(cur, user_id, hash_password(plaintext_password))

        results.append(
            {
                "user_id": user_id,
                "name": name,
                "email": email,
                "role": role_name,
                "created": created,
                "plaintext_password": plaintext_password,
                "password_env_var": password_env_var,
            }
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
        if r["plaintext_password"] is not None:
            print(f"    password (shown once, not stored anywhere): {r['plaintext_password']}")
            print(f"    add to .env as: {r['password_env_var']}={r['plaintext_password']}")
        else:
            print("    password: (unchanged, not shown)")


if __name__ == "__main__":
    main()
