"""Embedding generation using sentence-transformers/all-MiniLM-L6-v2,
producing 384-dim vectors matching the chunks.embedding column."""

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def load_model(model_name=EMBEDDING_MODEL_NAME):
    import torch
    from sentence_transformers import SentenceTransformer

    # Belt-and-suspenders alongside the Dockerfile's OMP_NUM_THREADS=1 --
    # this applies even when load_model() runs somewhere that env var
    # isn't set (e.g. a local venv), same reasoning: one request's worth
    # of embeddings at a time, extra threads just cost memory.
    torch.set_num_threads(1)
    return SentenceTransformer(model_name)


def embed_texts(model, texts, batch_size=32):
    """Batch-encode a list of chunk texts (from a single document) and
    return a list of plain Python float lists, one per text."""
    if not texts:
        return []

    embeddings = model.encode(
        texts, batch_size=batch_size, show_progress_bar=False
    )

    vectors = [vector.astype(float).tolist() for vector in embeddings]

    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"Expected {EMBEDDING_DIM}-dim embeddings, got {len(vector)}. "
                f"Is the model still all-MiniLM-L6-v2?"
            )

    return vectors
