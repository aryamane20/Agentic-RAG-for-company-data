"""Embedding generation using sentence-transformers/all-MiniLM-L6-v2,
producing 384-dim vectors matching the chunks.embedding column."""

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def load_model(model_name=EMBEDDING_MODEL_NAME):
    from sentence_transformers import SentenceTransformer

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
