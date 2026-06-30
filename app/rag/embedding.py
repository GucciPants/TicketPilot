"""Embedding generation using OpenRouter API."""
import os
import requests
from functools import lru_cache
from app.utils.retry import sync_retry


@lru_cache(maxsize=256)
@sync_retry(max_retries=3, exceptions=(requests.exceptions.RequestException,))
def get_embedding(text: str):
    """Generate embedding using OpenRouter API."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/text-embedding-3-small",
        "input": text,
        "dimensions": 384
    }
    response = requests.post(
        os.getenv("EMBEDDING_BASE_URL", "https://openrouter.ai/api/v1/embeddings"),
        headers=headers,
        json=payload,
        timeout=int(os.getenv("EMBEDDING_TIMEOUT", "60"))
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]
