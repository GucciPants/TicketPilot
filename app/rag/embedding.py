import os
import requests

def get_embedding(text: str):
    """Generate embedding using OpenRouter API."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        print("Warning: OPENROUTER_API_KEY not set, using fallback embedding")
        return [0.0] * 384
    
    try:
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
            timeout=30
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return [0.0] * 384
