"""DeepSeek LLM via the OpenAI-compatible endpoint."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from config.settings import settings


@lru_cache(maxsize=1)
def get_chat_model() -> Any:
    from langchain_core.language_models.chat_models import BaseChatModel

    if settings.demo_mode:
        raise RuntimeError("Demo mode does not use the LLM.")
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.3,
        max_retries=3,
    )