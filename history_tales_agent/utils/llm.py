"""LLM client wrapper with retry, rate limiting, and structured output."""

from __future__ import annotations

import json
import time
from typing import Any, Optional, Type

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from history_tales_agent.config import AppConfig, get_config
from history_tales_agent.utils.logging import get_logger
from history_tales_agent.utils.retry import retry_api_call

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, max_rpm: int = 20):
        self.max_rpm = max_rpm
        self.timestamps: list[float] = []

    def wait_if_needed(self) -> None:
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < 60]
        if len(self.timestamps) >= self.max_rpm:
            sleep_time = 60 - (now - self.timestamps[0]) + 0.5
            if sleep_time > 0:
                logger.info("rate_limit_wait", seconds=round(sleep_time, 1))
                time.sleep(sleep_time)
        self.timestamps.append(time.time())


_limiter: Optional[_RateLimiter] = None


def _get_limiter(config: AppConfig) -> _RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = _RateLimiter(max_rpm=config.max_requests_per_minute)
    return _limiter


# ---------------------------------------------------------------------------
# LLM singleton
# ---------------------------------------------------------------------------

_llm: Optional[ChatOpenAI] = None


def get_llm(config: AppConfig | None = None) -> ChatOpenAI:
    """Return (or create) the ChatOpenAI instance."""
    global _llm
    if _llm is None:
        cfg = config or get_config()
        _llm = ChatOpenAI(
            model=cfg.openai_model,
            temperature=cfg.openai_temperature,
            api_key=cfg.openai_api_key,
            max_retries=2,
            max_tokens=16384,
        )
    return _llm


# ---------------------------------------------------------------------------
# Call helpers
# ---------------------------------------------------------------------------


@retry_api_call
def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: AppConfig | None = None,
    temperature: float | None = None,
) -> str:
    """Call the LLM and return the text response."""
    cfg = config or get_config()
    _get_limiter(cfg).wait_if_needed()

    llm = get_llm(cfg)
    if temperature is not None:
        llm = llm.with_config({"temperature": temperature})

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    logger.debug(
        "llm_call",
        system_len=len(system_prompt),
        user_len=len(user_prompt),
        response_len=len(response.content),
    )
    return response.content


@retry_api_call
def call_llm_structured(
    system_prompt: str,
    user_prompt: str,
    output_schema: Type[BaseModel],
    config: AppConfig | None = None,
) -> BaseModel:
    """Call the LLM and parse the response into a Pydantic model."""
    cfg = config or get_config()
    _get_limiter(cfg).wait_if_needed()

    llm = get_llm(cfg)
    structured_llm = llm.with_structured_output(output_schema)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    result = structured_llm.invoke(messages)
    logger.debug("llm_structured_call", schema=output_schema.__name__)
    return result


@retry_api_call
def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    config: AppConfig | None = None,
) -> dict[str, Any]:
    """Call the LLM and parse JSON from the response."""
    raw = call_llm(system_prompt, user_prompt, config)
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)
