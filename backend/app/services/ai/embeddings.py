import hashlib
import math
from typing import List, Dict, Any
import numpy as np
import httpx
from backend.app.core.config import settings
from backend.app.core.logging import logger

EMBEDDING_DIM = settings.EMBEDDING_DIMENSION


class EmbeddingError(Exception):
    """Base exception for embedding generation and compatibility errors."""
    pass


class EmbeddingProviderError(EmbeddingError):
    """Raised when an external embedding provider (e.g. Gemini, OpenAI) fails."""
    pass


class EmbeddingMismatchError(EmbeddingError):
    """Raised when query embedding provider/model does not match stored document embeddings."""
    pass


def get_active_embedding_config() -> Dict[str, Any]:
    """
    Returns the currently active embedding configuration (provider, model, dimension).
    """
    provider = settings.active_provider
    if provider == "gemini":
        model = settings.EMBEDDING_MODEL
    elif provider == "openai":
        model = settings.EMBEDDING_MODEL
    else:
        model = "deterministic-demo-v1"

    return {
        "provider": provider,
        "model": model,
        "dimension": settings.EMBEDDING_DIMENSION
    }


def get_embedding(text: str) -> List[float]:
    """
    Get embedding for a single text.
    Raises EmbeddingProviderError if external embedding generation fails.
    """
    embeddings = get_embeddings([text])
    return embeddings[0] if embeddings else [0.0] * EMBEDDING_DIM


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Get embeddings for a list of texts.
    Dispatches strictly to settings.active_provider ('gemini', 'openai', 'demo').
    Raises EmbeddingProviderError on provider failure; does NOT silently fall back.
    """
    if not texts:
        return []

    active_provider = settings.active_provider

    if active_provider == "gemini":
        try:
            return _get_gemini_embeddings(texts)
        except Exception as e:
            # Log safe error without exposing raw exception messages, URLs, headers, or API keys
            err_type = type(e).__name__
            logger.error(f"Google Gemini embedding API call failed with exception type '{err_type}'. Request could not be completed.")
            raise EmbeddingProviderError(
                "Failed to generate embeddings from Google Gemini API. Service may be unavailable or rate limited."
            ) from None

    elif active_provider == "openai":
        try:
            return _get_openai_embeddings(texts)
        except Exception as e:
            # Log safe error without exposing raw exception messages, URLs, headers, or API keys
            err_type = type(e).__name__
            logger.error(f"OpenAI embedding API call failed with exception type '{err_type}'. Request could not be completed.")
            raise EmbeddingProviderError(
                "Failed to generate embeddings from OpenAI API. Service may be unavailable or rate limited."
            ) from None

    # Explicit Deterministic Demo Mode (activated only when LLM_PROVIDER=demo or no key configured)
    return [_generate_deterministic_embedding(t) for t in texts]


def _get_gemini_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings using the official Google Gen AI Python SDK (google-genai).
    Uses output_dimensionality to ensure vector length matches settings.EMBEDDING_DIMENSION.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    # Configure output dimensionality to match database vector column
    config = types.EmbedContentConfig(
        output_dimensionality=settings.EMBEDDING_DIMENSION
    )

    # Process in batches of up to 100 texts to prevent payload limit issues
    batch_size = 50
    all_embeddings: List[List[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=batch,
            config=config
        )
        if hasattr(response, "embeddings") and response.embeddings:
            for emb in response.embeddings:
                all_embeddings.append(emb.values)
        else:
            raise ValueError("No embeddings returned by Gemini API")

    return all_embeddings


def _get_openai_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using OpenAI REST API."""
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": texts,
        "model": settings.EMBEDDING_MODEL
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post("https://api.openai.com/v1/embeddings", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]


def _generate_deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Generates a deterministic, normalized dense vector for text.
    Ensures that words with similar semantics (e.g. refund, return, exchange; delivery, shipping, track)
    share overlapping dense vector components so cosine similarity search works realistically
    in Demo Mode without external network dependencies.
    """
    cleaned = text.lower()
    vec = np.zeros(dim, dtype=np.float32)

    # Core concept semantic topic anchors for Demo Mode
    topic_weights = {
        # Refund / Return cluster
        "refund": 10, "return": 10, "money back": 12, "exchange": 9, "reimburse": 8, "faulty": 7, "damaged": 7, "receipt": 6,
        # Shipping / Delivery cluster
        "shipping": 30, "delivery": 30, "carrier": 25, "courier": 25, "transit": 28, "dhl": 24, "fedex": 24, "usps": 24, "track": 26, "delay": 20,
        # Order / Cancellation cluster
        "order": 50, "purchase": 48, "item": 45, "invoice": 46, "cancel": 52, "modify": 47, "address": 49,
        # Policy / Warranty cluster
        "policy": 70, "terms": 70, "warranty": 72, "guarantee": 71, "privacy": 75, "hours": 68, "support": 65, "contact": 65
    }

    # Inject topic weights into designated vector coordinate zones
    for keyword, zone_start in topic_weights.items():
        if keyword in cleaned:
            freq = cleaned.count(keyword)
            for offset in range(12):
                idx = (zone_start + offset) % dim
                vec[idx] += 1.5 * freq * (1.0 / (offset + 1))

    # Incorporate word-level tokens and n-grams
    words = cleaned.split()
    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        for i in range(4):
            coord = (h >> (i * 8)) % dim
            sign = 1.0 if (h >> (i * 8 + 6)) & 1 else -1.0
            vec[coord] += sign * 0.4

    # Add character 3-grams for typo & morphological robustness
    for i in range(len(cleaned) - 2):
        trigram = cleaned[i:i+3]
        h_tri = int(hashlib.sha256(trigram.encode("utf-8")).hexdigest(), 16)
        coord = h_tri % dim
        vec[coord] += 0.05

    # L2 normalize
    norm = np.linalg.norm(vec)
    if norm > 1e-9:
        vec = vec / norm
    else:
        vec[0] = 1.0

    return vec.tolist()


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
