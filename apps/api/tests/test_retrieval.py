from app.retrieval import _hash_embedding, chunk_text, cosine_similarity


def test_hash_embedding_is_deterministic_and_normalized():
    first = _hash_embedding("missing title")
    second = _hash_embedding("missing title")

    assert first == second
    assert len(first) == 2048
    assert 0.99 < cosine_similarity(first, first) <= 1.01


def test_chunk_text_respects_character_budget():
    chunks = chunk_text("one. " * 100, max_chars=100)

    assert len(chunks) > 1
    assert all(len(chunk) <= 100 or len(chunk.split()) == 1 for chunk in chunks)
