# Role-Based Access Control Plan (Query-Time Permission Filtering)

This adds real permission enforcement to the query pipeline. Until now,
`search_documents` returned the top matches from every chunk in the
database regardless of who was asking -- `document_roles` existed in the
schema but nothing at query time actually checked it. This plan closes
that gap.

## 1. Seed script (`seed_test_users.py`, project root)

- Creates one user per existing role: `hr_staff`, `engineer`, `executive`.
  - `Test HR Staff` / `hr_staff_test@example.com`
  - `Test Engineer` / `engineer_test@example.com`
  - `Test Executive` / `executive_test@example.com`
- **Idempotent, keyed on email** -- `users.email` already has a `UNIQUE`
  constraint in `schema.sql`. Lookup-or-insert: if a user with that email
  exists, reuse its `id`; otherwise insert and report the new `id`.
  Re-running the script never creates duplicates.
- Reuses `ingestion.db.get_connection()` and `ingestion.db.get_role_id_map()`
  (already generic) instead of hardcoding role IDs.
- Prints all 3 user IDs at the end -- these are what you reference in
  testing and in the CLI's "run as" prompt.
- Multiple users can share the same role (e.g. a second engineer with a
  different email) -- dedup only keys on email, not role. `role_id` is a
  plain foreign key, not unique, so this is expected, normal-DB behavior.

## 2. Permission-scoped search (`qa/retrieval.py`)

`search_chunks(cur, query_vector, user_id, top_k=5)` -- `user_id` becomes
a required parameter.

```sql
SELECT c.content, d.filename, (c.embedding <=> %s::vector) AS distance
FROM chunks c
JOIN documents d ON d.id = c.document_id
JOIN document_roles dr ON dr.document_id = d.id
WHERE dr.role_id = (SELECT role_id FROM users WHERE id = %s)
ORDER BY distance
LIMIT %s;
```

- Still uses the HNSW index exactly as before (`<=>`, `vector_cosine_ops`)
  -- the permission joins only narrow which rows are eligible before
  ranking, they don't change the distance computation.
- **Fails closed for free**: an unknown `user_id` makes the subquery
  return `NULL`; `dr.role_id = NULL` is never true in SQL, so the query
  returns zero rows rather than erroring or matching everything.
- `embed_question()` is unchanged.

## 3. Tool update (`qa/tools.py`)

- `build_search_tool(cur, embed_model, user_id, top_k=..., on_search=...)`
  -- `user_id` becomes a required factory argument, bound into the
  closure when the tool is built.
- The tool's callable signature the model actually sees stays
  `search_documents(query: str)` only. `user_id` is never exposed to the
  model as an argument, never mentioned in the tool's name/description/
  schema. The model cannot see, choose, or override it -- the permission
  boundary is enforced entirely outside the model's control.

## 4. CLI update (`ask.py`)

- At startup, once, before the question loop: prompt
  `"Run as which test user? (enter user_id): "`.
- That `user_id` is held in a variable for the whole session and passed
  into `build_search_tool()` -- no re-prompting per question.
- This is a manual stand-in for real authentication. Later, a real login/
  session system would supply `user_id` automatically instead of a typed
  prompt -- the SQL query and the "model never sees user_id" design don't
  change when that happens; only where `user_id` comes from changes.

## Testing

- `qa/retrieval.py`: mocked-cursor test asserting the new SQL includes the
  role-filtering subquery and correct params (`query_vector, user_id,
  top_k`).
- `qa/tools.py`: test asserting `build_search_tool` binds `user_id` into
  the closure without it appearing in the tool's exposed args schema.
- `seed_test_users.py`: testable lookup-or-insert function, tested with a
  mocked cursor for both the "user exists" and "user doesn't exist" paths.

## Validation

After implementation: run the seed script to get 3 real user IDs. Ask the
same finance-related question (e.g. "What are the company's major vendor
commitments?") twice:
- as the `engineer` user -- expect zero results (finance docs excluded
  from `document_roles` for that role)
- as the `executive` user -- expect real results

Both outputs shown side by side to confirm the filter is actually working,
not just assumed to work.
