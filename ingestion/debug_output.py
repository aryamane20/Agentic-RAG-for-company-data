"""Write human-inspectable JSON snapshots of each pipeline stage to a
debug_output/ directory, so the ingestion run can be sanity-checked
without querying Postgres by hand."""

import json
import os

EMBEDDING_PREVIEW_LEN = 5


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_policy_resolution(output_dir, resolved_docs, warnings):
    """Dump what Part 2 (policy mapping) decided for every document."""
    data = {
        "resolved_documents": [
            {
                "relative_path": d.relative_path,
                "filename": d.filename,
                "department": d.department,
                "allowed_roles": d.allowed_roles,
                "matched_rule": d.matched_rule,
                "used_default_rule": d.used_default_rule,
            }
            for d in resolved_docs
        ],
        "warnings": warnings,
    }
    _write_json(os.path.join(output_dir, "policy_resolution.json"), data)


def build_chunk_debug_payload(resolved_doc, chunk_texts, vectors):
    """Build the JSON-serializable dict for one document's chunk/embedding
    breakdown. Split out from the file write so it's independently testable."""
    chunks = []
    for i, (text, vector) in enumerate(zip(chunk_texts, vectors)):
        chunks.append(
            {
                "index": i,
                "char_count": len(text),
                "content": text,
                "embedding_dim": len(vector),
                "embedding_preview": vector[:EMBEDDING_PREVIEW_LEN],
            }
        )

    return {
        "relative_path": resolved_doc.relative_path,
        "filename": resolved_doc.filename,
        "department": resolved_doc.department,
        "allowed_roles": resolved_doc.allowed_roles,
        "used_default_rule": resolved_doc.used_default_rule,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def write_chunk_debug(output_dir, resolved_doc, chunk_texts, vectors):
    """Write one JSON file per document under chunks/<department>/<filename>.json"""
    payload = build_chunk_debug_payload(resolved_doc, chunk_texts, vectors)
    out_name = os.path.splitext(resolved_doc.filename)[0] + ".json"
    path = os.path.join(output_dir, "chunks", resolved_doc.department, out_name)
    _write_json(path, payload)


def write_db_snapshot(output_dir, cur):
    """Read back the actual rows written to Postgres and dump them, so the
    real DB state (not just what the script intended to write) is visible."""
    cur.execute("SELECT id, filename, department FROM documents ORDER BY filename")
    documents = [
        {"id": row[0], "filename": row[1], "department": row[2]}
        for row in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT d.filename, r.name
        FROM document_roles dr
        JOIN documents d ON d.id = dr.document_id
        JOIN roles r ON r.id = dr.role_id
        ORDER BY d.filename, r.name
        """
    )
    document_roles = [{"filename": row[0], "role": row[1]} for row in cur.fetchall()]

    cur.execute(
        """
        SELECT d.filename, c.id, c.content
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        ORDER BY d.filename, c.id
        """
    )
    chunks = [
        {"filename": row[0], "chunk_id": row[1], "content": row[2]}
        for row in cur.fetchall()
    ]

    _write_json(os.path.join(output_dir, "db_snapshot", "documents.json"), documents)
    _write_json(
        os.path.join(output_dir, "db_snapshot", "document_roles.json"), document_roles
    )
    _write_json(os.path.join(output_dir, "db_snapshot", "chunks.json"), chunks)
