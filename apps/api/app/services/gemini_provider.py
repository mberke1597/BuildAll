"""
Gemini AI Provider for BuildAll
Uses Google's Generative AI (Gemini) for embeddings and chat completions.
"""
import os
from typing import List

import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

EMBED_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "embedding-001")
CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-flash")


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using Gemini.
    Returns a list of embedding vectors.
    """
    embeddings = []
    for text in texts:
        result = genai.embed_content(
            model=f"models/{EMBED_MODEL}",
            content=text,
            task_type="retrieval_document",
        )
        embeddings.append(result["embedding"])
    return embeddings


def chat_completion(system_prompt: str, user_prompt: str) -> str:
    """
    Generate a chat completion using Gemini.
    Combines system and user prompts since Gemini doesn't have explicit system role.
    """
    model = genai.GenerativeModel(
        CHAT_MODEL,
        system_instruction=system_prompt,
    )
    response = model.generate_content(user_prompt)
    return response.text
