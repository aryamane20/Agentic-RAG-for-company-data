#!/usr/bin/env python3
"""Ingest department markdown docs into Postgres: chunk on ## sections,
embed with all-MiniLM-L6-v2, and write documents/document_roles/chunks
per access_policy.json's role mapping."""

import os
import shutil
import sys

from ingestion import chunking, db, debug_output, embeddings, policy

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
POLICY_PATH = os.path.join(ROOT_DIR, "access_policy.json")
DEPARTMENT_FOLDERS = ["hr", "engineering", "finance"]
CHUNK_CAP = chunking.DEFAULT_CHUNK_CAP
DEBUG_DIR = os.path.join(ROOT_DIR, "debug_output")


def process_document(cur, role_id_map, resolved_doc, model):
    path = os.path.join(ROOT_DIR, resolved_doc.relative_path)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    chunk_texts = chunking.chunk_markdown(text, cap=CHUNK_CAP)
    vectors = embeddings.embed_texts(model, chunk_texts)

    replaced = db.delete_document_if_exists(cur, resolved_doc.filename)
    document_id = db.insert_document(cur, resolved_doc.filename, resolved_doc.department)

    role_ids = []
    for role_name in resolved_doc.allowed_roles:
        if role_name not in role_id_map:
            raise ValueError(
                f"Role '{role_name}' from access_policy.json is not in the "
                f"roles table (seeded roles: {sorted(role_id_map)})"
            )
        role_ids.append(role_id_map[role_name])
    db.insert_document_roles(cur, document_id, role_ids)

    db.insert_chunks(cur, document_id, chunk_texts, vectors)

    # Written only after every DB write above succeeded -- if anything
    # raised, we never reach here, so debug_output never shows a document
    # as ingested unless it actually was (the transaction still isn't
    # committed until the caller's `with conn:` block exits, but nothing
    # past this point can fail for this document).
    debug_output.write_chunk_debug(DEBUG_DIR, resolved_doc, chunk_texts, vectors)

    return {
        "relative_path": resolved_doc.relative_path,
        "filename": resolved_doc.filename,
        "department": resolved_doc.department,
        "allowed_roles": resolved_doc.allowed_roles,
        "used_default_rule": resolved_doc.used_default_rule,
        "chunk_count": len(chunk_texts),
        "replaced": replaced,
    }


def main():
    if os.path.isdir(DEBUG_DIR):
        shutil.rmtree(DEBUG_DIR)

    policy_data = policy.load_policy(POLICY_PATH)

    try:
        policy_index = policy.build_policy_index(policy_data)
    except policy.PolicyConflictError as exc:
        print(f"POLICY CONFLICT: {exc}")
        sys.exit(1)

    discovered = policy.discover_documents(ROOT_DIR, DEPARTMENT_FOLDERS)
    resolved_docs, warnings = policy.resolve_documents(
        discovered, policy_index, policy_data.get("default_rule", {})
    )
    warnings.extend(
        f"access_policy.json references '{p}' but no such file was found on disk"
        for p in policy.find_missing_policy_files(discovered, policy_index)
    )

    debug_output.write_policy_resolution(DEBUG_DIR, resolved_docs, warnings)

    print(f"Loading embedding model ({embeddings.EMBEDDING_MODEL_NAME})...")
    model = embeddings.load_model()

    conn = db.get_connection()
    results = []
    failures = []
    try:
        with conn.cursor() as setup_cur:
            role_id_map = db.get_role_id_map(setup_cur)

        for resolved_doc in resolved_docs:
            try:
                with conn:
                    with conn.cursor() as cur:
                        result = process_document(cur, role_id_map, resolved_doc, model)
                results.append(result)
            except Exception as exc:  # noqa: BLE001 - report and continue
                conn.rollback()
                failures.append((resolved_doc.relative_path, str(exc)))

        with conn.cursor() as snapshot_cur:
            debug_output.write_db_snapshot(DEBUG_DIR, snapshot_cur)
    finally:
        conn.close()

    print_summary(results, warnings, failures)
    print(f"Debug output written to: {DEBUG_DIR}")

    if failures:
        sys.exit(1)


def print_summary(results, warnings, failures):
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)

    created = [r for r in results if not r["replaced"]]
    replaced = [r for r in results if r["replaced"]]
    print(
        f"\nDocuments processed: {len(results)} "
        f"({len(created)} created, {len(replaced)} replaced)"
    )

    for r in results:
        default_note = " [DEFAULTED - see warnings]" if r["used_default_rule"] else ""
        print(
            f"\n  {r['relative_path']}{default_note}\n"
            f"    department: {r['department']}\n"
            f"    chunks:     {r['chunk_count']}\n"
            f"    roles:      {', '.join(r['allowed_roles'])}"
        )

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for path, err in failures:
            print(f"  - {path}: {err}")

    print()


if __name__ == "__main__":
    main()
