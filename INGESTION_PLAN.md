# Ingestion Pipeline Plan

## 0. File layout

Docs live under department subfolders matching `access_policy.json` exactly:

```
hr/employee_handbook.md
hr/benefits_guide.md
hr/compensation_bands.md
engineering/system_architecture.md
engineering/api_design_guidelines.md
engineering/incident_postmortem.md
engineering/on_call_runbook.md
finance/annual_budget_summary.md
finance/board_deck_excerpt.md
finance/vendor_contract_summary.md
```

## 1. Chunking

- Split each file on lines starting with `## ` (level-2 headers).
- Any text before the first `##` (title, "Last updated" line, etc.) is prepended to the first section rather than becoming its own orphan chunk.
- Each section (header + body) is one chunk, as long as it fits under the size cap.
- **Size cap**: ~1500 characters per chunk. If a section exceeds it, split on paragraph boundaries (blank-line-separated), greedily packing paragraphs up to the cap. If a single paragraph itself exceeds the cap, fall back to sentence-boundary splitting.
- Every sub-chunk gets its section's `## Header` line re-prepended, so embeddings never lose section context.
- Chunk text is stored (and embedded) exactly as constructed, header included.

## 2. Policy mapping (`access_policy.json` → department + allowed roles)

- Build a reverse index at startup: for every rule under `department_rules`, for every path in its `folders` list, map `path → allowed_roles`.
- Walk `hr/`, `engineering/`, `finance/` on disk; for each `.md` file found, look up its relative path (e.g. `hr/employee_handbook.md`) in the index.
- `documents.department` = the folder name (`hr` / `engineering` / `finance`). The specific rule key (e.g. `hr_general` vs `hr_restricted`) is only used transiently to pull `allowed_roles` — it is never stored.

**Conflict handling**: if the same file path appears in more than one rule's `folders` list, this is treated as a bug in the policy file, not something to resolve automatically. The script hard-stops before writing anything to the database, printing which file and which two rule keys collided.

**Fallback — file on disk, not listed in any rule**: apply `default_rule` (`allowed_roles: ["executive"]`), print a loud warning, and continue. Fail-closed (most restrictive), never silently skipped, never silently over-exposed.

**Fallback — policy references a file that doesn't exist on disk**: print a warning, skip it, continue. Not a security risk, likely a stale policy entry.

## 3. Embeddings

- Model: `sentence-transformers`' `all-MiniLM-L6-v2`, loaded once at script start (not per-chunk/per-document).
- Native output is 384-dim, matching `chunks.embedding vector(384)` exactly — no truncation/padding.
- Batch-encode all chunks **within a single document** in one `model.encode(...)` call (not one global batch across all documents, not one call per chunk).
- Convert each embedding from numpy `float32` array to a plain Python list before writing (via the `pgvector` psycopg2 adapter).
- No normalization needed — HNSW index uses `vector_cosine_ops`, and cosine distance is scale-invariant.
- Chunk text is embedded exactly as stored, including the prepended section header.

## 4. Database writes

- Connect via `psycopg2` using the credentials from `docker-compose.yml` (`rag_user` / `rag_password` / `rag_db` @ `localhost:5435`). Register the `pgvector` adapter for direct list/array → `vector` inserts.
- **Per document** (not three global passes across all documents), in one transaction:
  1. `INSERT INTO documents (filename, department) ... RETURNING id`
  2. For each resolved allowed role, look up `role_id` from `roles` and `INSERT INTO document_roles (document_id, role_id)`
  3. Chunk + embed the file, then `INSERT INTO chunks (document_id, content, embedding)` per chunk
- If any step for a document fails, roll back only that document's transaction, log the error, and continue to the next file — one bad document doesn't abort the whole run and never leaves partial/orphaned rows (e.g. chunks with no corresponding permissions).

**Rerun safety (delete-and-replace)**: before inserting a document, check if a `documents` row with that filename already exists. If so, delete it first — `document_roles` and `chunks` cascade-delete automatically (`ON DELETE CASCADE` already in `schema.sql`) — then insert fresh. Re-running the script after editing a doc is safe and produces an up-to-date copy, never duplicates.

**Update strategy**: whole-document delete-and-replace (Approach A), not chunk-level incremental re-embedding (Approach B). Re-embedding a full document with a local, free model over a small corpus is effectively instant, so the extra complexity of chunk-level diffing (stable chunk identity via content hashing, handling boundary shifts when edits move section text around) isn't justified yet. Revisit if the corpus grows large or embedding becomes costly (e.g. a paid API).

## 5. End-of-run summary

Printed after processing all files, without needing to query the database manually:
- Total documents processed (created vs replaced)
- Chunk count per document
- Permission mapping written per document (department + allowed roles)
- Any warnings (unclassified/defaulted files, policy entries with missing files)
- Any per-document failures (with the file skipped, not the whole run aborted)
