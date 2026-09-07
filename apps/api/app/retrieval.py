from __future__ import annotations

import hashlib
import math
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DocumentChunk
from .settings import Settings


def _hash_embedding(text: str, dimensions: int = 2048) -> list[float]:
    """Deterministic local fallback so the product is runnable without NIM."""

    values = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        values[index] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


async def embed_text(text: str, settings: Settings) -> list[float]:
    if not settings.nvidia_api_key:
        return _hash_embedding(text)
    async with httpx.AsyncClient(timeout=settings.nim_timeout_seconds) as client:
        response = await client.post(
            f"{settings.nvidia_nim_base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
            json={"model": settings.nvidia_nim_embed_model, "input": text},
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


def chunk_text(text: str, max_chars: int = 2400) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n+|(?<=[.!?])\s+", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= max_chars:
            current = f"{current} {paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
    return dot / (left_norm * right_norm)


def search_chunks(db: Session, project_id: str, query: str, limit: int = 8) -> list[tuple[DocumentChunk, float]]:
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    query_embedding = _hash_embedding(query)
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.project_id == project_id)).all()
    scored: list[tuple[DocumentChunk, float]] = []
    for chunk in chunks:
        content_tokens = set(re.findall(r"[a-z0-9]+", chunk.content.lower()))
        lexical = len(query_tokens & content_tokens) / max(len(query_tokens), 1)
        semantic = cosine_similarity(query_embedding, chunk.embedding or [])
        score = 0.55 * lexical + 0.45 * max(semantic, 0.0)
        if score > 0:
            scored.append((chunk, score))
    return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]
