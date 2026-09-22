from unittest.mock import MagicMock

from qa.retrieval import embed_question, search_chunks


class FakeModel:
    def encode(self, texts, batch_size=32, show_progress_bar=False):
        import numpy as np

        return np.ones((len(texts), 384), dtype=np.float32)


def test_embed_question_returns_single_384_dim_vector():
    model = FakeModel()

    vector = embed_question(model, "What is the PTO policy?")

    assert isinstance(vector, list)
    assert len(vector) == 384
    assert all(isinstance(x, float) for x in vector)


def test_search_chunks_runs_cosine_query_and_returns_dicts():
    cur = MagicMock()
    cur.fetchall.return_value = [
        ("## PTO\n\nbody", "employee_handbook.md", 0.12),
        ("## Leave\n\nbody", "benefits_guide.md", 0.34),
    ]
    query_vector = [0.1] * 384

    results = search_chunks(cur, query_vector, user_id=2, top_k=5)

    cur.execute.assert_called_once()
    executed_sql, params = cur.execute.call_args[0]
    assert "<=>" in executed_sql
    assert "<->" not in executed_sql
    assert "document_roles" in executed_sql
    assert "FROM users WHERE id = %s" in executed_sql
    assert params == (query_vector, 2, 5)

    assert results == [
        {"content": "## PTO\n\nbody", "filename": "employee_handbook.md", "distance": 0.12},
        {"content": "## Leave\n\nbody", "filename": "benefits_guide.md", "distance": 0.34},
    ]


def test_search_chunks_default_top_k_is_5():
    cur = MagicMock()
    cur.fetchall.return_value = []

    search_chunks(cur, [0.1] * 384, user_id=1)

    _, params = cur.execute.call_args[0]
    assert params[2] == 5


def test_search_chunks_requires_user_id():
    cur = MagicMock()
    cur.fetchall.return_value = []

    # user_id is a required positional/keyword arg now, not optional
    import inspect

    from qa.retrieval import search_chunks as fn

    sig = inspect.signature(fn)
    assert "user_id" in sig.parameters
    assert sig.parameters["user_id"].default is inspect.Parameter.empty
