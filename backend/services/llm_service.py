"""OpenAI chat completions with concurrency control."""

import asyncio
import json
import re
from typing import Any

from openai import OpenAI

from backend.config.settings import get_settings

_llm_semaphore: asyncio.Semaphore | None = None


def get_llm_semaphore() -> asyncio.Semaphore:
    global _llm_semaphore
    if _llm_semaphore is None:
        settings = get_settings()
        _llm_semaphore = asyncio.Semaphore(settings.max_llm_concurrent)
    return _llm_semaphore


class OpenAILLMService:
    def __init__(self) -> None:
        settings = get_settings()
        settings.require_openai()
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_chat_model

    @property
    def model_name(self) -> str:
        return self._model

    def chat_json_sync(
        self,
        system_prompt: str,
        user_content: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> dict[str, Any]:
        """Synchronous JSON extraction (used from LangGraph sync nodes)."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = (response.choices[0].message.content or "").strip()
        return self._parse_json_content(content)

    async def chat_json_async(
        self,
        system_prompt: str,
        user_content: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> dict[str, Any]:
        async with get_llm_semaphore():
            return await asyncio.to_thread(
                self.chat_json_sync,
                system_prompt,
                user_content,
                temperature=temperature,
                max_tokens=max_tokens,
            )

    def chat_text_sync(
        self,
        system_prompt: str,
        user_content: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 400,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    @staticmethod
    def _parse_json_content(content: str) -> dict[str, Any]:
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        return json.loads(content)
