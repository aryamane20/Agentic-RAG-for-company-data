import numpy as np
import pytest

from ingestion.embeddings import EMBEDDING_DIM, embed_texts


class FakeModel:
    """Stands in for SentenceTransformer so tests don't load a real model."""

    def __init__(self, dim=EMBEDDING_DIM):
        self.dim = dim
        self.last_call = None

    def encode(self, texts, batch_size=32, show_progress_bar=False):
        self.last_call = {"texts": texts, "batch_size": batch_size}
        return np.ones((len(texts), self.dim), dtype=np.float32)


def test_embed_texts_returns_plain_lists_of_correct_dimension():
    model = FakeModel()
    texts = ["## A\n\nbody a", "## B\n\nbody b"]

    vectors = embed_texts(model, texts)

    assert len(vectors) == 2
    for v in vectors:
        assert isinstance(v, list)
        assert len(v) == EMBEDDING_DIM
        assert all(isinstance(x, float) for x in v)


def test_embed_texts_empty_input_returns_empty_list():
    model = FakeModel()

    assert embed_texts(model, []) == []
    assert model.last_call is None


def test_embed_texts_batches_all_chunks_in_a_single_encode_call():
    model = FakeModel()
    texts = [f"chunk {i}" for i in range(5)]

    embed_texts(model, texts, batch_size=32)

    assert model.last_call["texts"] == texts
    assert model.last_call["batch_size"] == 32


def test_embed_texts_raises_on_dimension_mismatch():
    model = FakeModel(dim=100)  # wrong model, wrong dimension

    with pytest.raises(ValueError):
        embed_texts(model, ["some text"])
