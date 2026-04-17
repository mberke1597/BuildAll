"""
AI Provider Factory
Supports both Gemini and OpenAI based on AI_PROVIDER env variable.
Includes streaming support for SSE endpoints.
"""
from typing import AsyncIterator, Dict, List, Optional
import os


class AIProvider:
    """Abstract base class for AI providers"""

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def chat(self, system: str, user: str) -> str:
        raise NotImplementedError

    def chat_with_history(self, system: str, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        """Chat with full message history. Default falls back to last user message."""
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return self.chat(system, last_user)

    def chat_stream(self, system: str, messages: List[Dict[str, str]], temperature: float = 0.2):
        """Synchronous generator yielding token deltas. Override per provider."""
        # Fallback: yield full response at once
        answer = self.chat_with_history(system, messages, temperature)
        yield answer

    def chat_stream_with_usage(self, system: str, messages: List[Dict[str, str]], temperature: float = 0.2):
        """Generator yielding (delta, usage_dict_or_none). Last yield has usage."""
        for delta in self.chat_stream(system, messages, temperature):
            yield delta, None


class GeminiProvider(AIProvider):
    """Gemini AI Provider"""

    def __init__(self):
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        genai.configure(api_key=api_key)
        self.genai = genai
        self.embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "embedding-001")
        self.chat_model = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-flash")

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            result = self.genai.embed_content(
                model=f"models/{self.embedding_model}",
                content=text,
                task_type="retrieval_document",
            )
            embeddings.append(result["embedding"])
        return embeddings

    def chat(self, system: str, user: str) -> str:
        model = self.genai.GenerativeModel(
            self.chat_model,
            system_instruction=system,
        )
        response = model.generate_content(user)
        return response.text

    def chat_with_history(self, system: str, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        model = self.genai.GenerativeModel(self.chat_model, system_instruction=system)
        # Gemini uses a flat contents list
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [m["content"]]})
        response = model.generate_content(contents)
        return response.text

    def chat_stream(self, system: str, messages: List[Dict[str, str]], temperature: float = 0.2):
        model = self.genai.GenerativeModel(self.chat_model, system_instruction=system)
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [m["content"]]})
        response = model.generate_content(contents, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text


class OpenAIProvider(AIProvider):
    """OpenAI Provider"""

    def __init__(self):
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")

        self.client = OpenAI(api_key=api_key)
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    def embed(self, texts: List[str]) -> List[List[float]]:
        res = self.client.embeddings.create(model=self.embedding_model, input=texts)
        return [item.embedding for item in res.data]

    def chat(self, system: str, user: str) -> str:
        res = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return res.choices[0].message.content

    def chat_with_history(self, system: str, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        all_messages = [{"role": "system", "content": system}] + messages
        res = self.client.chat.completions.create(
            model=self.chat_model,
            messages=all_messages,
            temperature=temperature,
        )
        return res.choices[0].message.content

    def chat_stream(self, system: str, messages: List[Dict[str, str]], temperature: float = 0.2):
        all_messages = [{"role": "system", "content": system}] + messages
        stream = self.client.chat.completions.create(
            model=self.chat_model,
            messages=all_messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices[0].delta else None
            if delta:
                yield delta

    def chat_stream_with_usage(self, system: str, messages: List[Dict[str, str]], temperature: float = 0.2):
        all_messages = [{"role": "system", "content": system}] + messages
        stream = self.client.chat.completions.create(
            model=self.chat_model,
            messages=all_messages,
            temperature=temperature,
            stream=True,
            stream_options={"include_usage": True},
        )
        usage = None
        for chunk in stream:
            if chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            delta = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta else None
            if delta:
                yield delta, None
        # Final yield with usage
        if usage:
            yield "", usage


def get_ai_provider() -> AIProvider:
    """
    Factory function to get the appropriate AI provider.
    Uses AI_PROVIDER env variable to determine which provider to use.
    Defaults to 'gemini' if not specified.
    """
    provider = os.getenv("AI_PROVIDER", "gemini").lower()

    if provider == "gemini":
        return GeminiProvider()
    elif provider == "openai":
        return OpenAIProvider()
    else:
        raise ValueError(f"Unknown AI provider: {provider}. Use 'gemini' or 'openai'")

