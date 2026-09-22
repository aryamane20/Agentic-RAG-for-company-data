from unittest.mock import MagicMock

from qa.tools import build_search_tool, format_chunks_for_model


def test_format_chunks_for_model_includes_filename_and_content_no_distance():
    chunks = [
        {"content": "## PTO\n\nbody a", "filename": "employee_handbook.md", "distance": 0.12},
        {"content": "## Leave\n\nbody b", "filename": "benefits_guide.md", "distance": 0.34},
    ]

    text = format_chunks_for_model(chunks)

    assert "[Source: employee_handbook.md]" in text
    assert "## PTO\n\nbody a" in text
    assert "[Source: benefits_guide.md]" in text
    assert "0.12" not in text
    assert "0.34" not in text
    assert "distance" not in text.lower()


def test_format_chunks_for_model_empty_results():
    assert format_chunks_for_model([]) == "No matching results found."


class FakeEmbedModel:
    def encode(self, texts, batch_size=32, show_progress_bar=False):
        import numpy as np

        return np.ones((len(texts), 384), dtype=np.float32)


def test_search_tool_runs_search_and_returns_formatted_string():
    cur = MagicMock()
    cur.fetchall.return_value = [("## PTO\n\nbody", "employee_handbook.md", 0.1)]

    tool = build_search_tool(cur, FakeEmbedModel(), user_id=2)
    result = tool.func(query="how much PTO do employees get")

    assert "[Source: employee_handbook.md]" in result
    assert "## PTO\n\nbody" in result
    assert "0.1" not in result


def test_search_tool_passes_bound_user_id_to_search_chunks():
    cur = MagicMock()
    cur.fetchall.return_value = []

    tool = build_search_tool(cur, FakeEmbedModel(), user_id=3)
    tool.func(query="vendor commitments")

    executed_sql, params = cur.execute.call_args[0]
    assert params[1] == 3  # user_id slot in (query_vector, user_id, top_k)


def test_search_tool_calls_on_search_callback_with_query_and_chunks():
    cur = MagicMock()
    cur.fetchall.return_value = [("## PTO\n\nbody", "employee_handbook.md", 0.1)]
    calls = []

    tool = build_search_tool(
        cur, FakeEmbedModel(), user_id=2, on_search=lambda q, c: calls.append((q, c))
    )
    tool.func(query="pto policy")

    assert len(calls) == 1
    query, chunks = calls[0]
    assert query == "pto policy"
    assert chunks == [{"content": "## PTO\n\nbody", "filename": "employee_handbook.md", "distance": 0.1}]


def test_search_tool_has_expected_name_and_no_behavioral_instructions_in_description():
    tool = build_search_tool(MagicMock(), FakeEmbedModel(), user_id=1)

    assert tool.name == "search_documents"
    # description should describe the tool only, not restate system-prompt rules
    assert "own knowledge" not in tool.description
    assert "must call" not in tool.description.lower()
    assert "excerpts" in tool.description


def test_search_tool_user_id_is_not_exposed_to_the_model():
    tool = build_search_tool(MagicMock(), FakeEmbedModel(), user_id=42)

    # the only field the model can see/set is "query" -- user_id must not
    # appear anywhere in the tool's schema, name, or description
    schema_fields = tool.args_schema.model_fields.keys()
    assert list(schema_fields) == ["query"]
    assert "user_id" not in tool.description.lower()
    assert "42" not in tool.description
