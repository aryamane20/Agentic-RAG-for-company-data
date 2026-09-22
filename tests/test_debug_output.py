import json
import os
from unittest.mock import MagicMock

from ingestion.debug_output import (
    build_chunk_debug_payload,
    write_chunk_debug,
    write_db_snapshot,
    write_policy_resolution,
)
from ingestion.policy import ResolvedDocument


def _sample_doc():
    return ResolvedDocument(
        relative_path="hr/benefits_guide.md",
        filename="benefits_guide.md",
        department="hr",
        allowed_roles=["hr_staff", "engineer", "executive"],
        used_default_rule=False,
        matched_rule="hr_general",
    )


def test_build_chunk_debug_payload_previews_embedding_without_full_vector():
    doc = _sample_doc()
    chunk_texts = ["## Welcome\n\nbody"]
    vectors = [[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]]

    payload = build_chunk_debug_payload(doc, chunk_texts, vectors)

    assert payload["filename"] == "benefits_guide.md"
    assert payload["chunk_count"] == 1
    chunk = payload["chunks"][0]
    assert chunk["content"] == "## Welcome\n\nbody"
    assert chunk["embedding_dim"] == 7
    assert chunk["embedding_preview"] == [0.1, 0.2, 0.3, 0.4, 0.5]
    assert "embedding" not in chunk  # no full vector


def test_write_chunk_debug_creates_file_under_department_folder(tmp_path):
    doc = _sample_doc()
    write_chunk_debug(str(tmp_path), doc, ["## A\n\nbody"], [[0.1] * 384])

    out_path = tmp_path / "chunks" / "hr" / "benefits_guide.json"
    assert out_path.exists()

    data = json.loads(out_path.read_text())
    assert data["department"] == "hr"
    assert data["chunk_count"] == 1


def test_write_policy_resolution_includes_warnings(tmp_path):
    doc = _sample_doc()
    write_policy_resolution(str(tmp_path), [doc], ["some warning"])

    out_path = tmp_path / "policy_resolution.json"
    data = json.loads(out_path.read_text())

    assert data["warnings"] == ["some warning"]
    assert data["resolved_documents"][0]["filename"] == "benefits_guide.md"


def test_write_db_snapshot_queries_and_writes_three_files(tmp_path):
    cur = MagicMock()
    cur.fetchall.side_effect = [
        [(1, "benefits_guide.md", "hr")],
        [("benefits_guide.md", "hr_staff")],
        [("benefits_guide.md", 10, "## Welcome\n\nbody")],
    ]

    write_db_snapshot(str(tmp_path), cur)

    documents = json.loads((tmp_path / "db_snapshot" / "documents.json").read_text())
    roles = json.loads((tmp_path / "db_snapshot" / "document_roles.json").read_text())
    chunks = json.loads((tmp_path / "db_snapshot" / "chunks.json").read_text())

    assert documents == [{"id": 1, "filename": "benefits_guide.md", "department": "hr"}]
    assert roles == [{"filename": "benefits_guide.md", "role": "hr_staff"}]
    assert chunks == [
        {"filename": "benefits_guide.md", "chunk_id": 10, "content": "## Welcome\n\nbody"}
    ]
