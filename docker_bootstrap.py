#!/usr/bin/env python3
"""Runs once, before uvicorn starts, on every container boot (see
docker-entrypoint.sh). Seeds test users and ingests the document corpus
only if the database doesn't already have them -- an existing database
with data already in it skips straight through. Both seed_test_users.py
and ingest.py are already safe to re-run on their own (upsert-by-email,
delete-and-replace-by-filename); the emptiness checks here just avoid
paying for that redundant work on every normal restart, not correctness."""

import subprocess
import sys

from ingestion import db


def _table_is_empty(cur, table_name):
    # table_name is always one of the two hardcoded literals below, never
    # external input -- an f-string here isn't a SQL-injection concern.
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cur.fetchone()[0] == 0


def main():
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            needs_seed = _table_is_empty(cur, "users")
            needs_ingest = _table_is_empty(cur, "chunks")
    finally:
        conn.close()

    if needs_seed:
        print("[bootstrap] users table is empty -- seeding test users", flush=True)
        subprocess.run([sys.executable, "seed_test_users.py"], check=True)
    else:
        print("[bootstrap] users table already populated -- skipping seed", flush=True)

    if needs_ingest:
        print("[bootstrap] chunks table is empty -- running ingestion", flush=True)
        subprocess.run([sys.executable, "ingest.py"], check=True)
    else:
        print("[bootstrap] chunks table already populated -- skipping ingestion", flush=True)


if __name__ == "__main__":
    main()
