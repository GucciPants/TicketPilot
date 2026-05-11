"""Embedding generation using OpenRouter API."""
import os
import requests
from functools import lru_cache


@lru_cache(maxsize=256)
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
        "https://openrouter.ai/api/v1/embeddings",
        headers=headers,
        json=payload,
        timeout=15
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]
