"""Thin wrappers around Anthropic and OpenAI for week-1 smoke testing.

We deliberately don't introduce LangChain / LlamaIndex yet — using the raw
SDKs first builds the right mental model for later weeks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from icd_mapper.config import settings

log = logging.getLogger(__name__)


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


# Rough public prices in USD per 1M tokens, as of May 2026.
# Update these if you change models — used for cost telemetry only.
PRICES = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


def _cost(model: str, in_tokens: int, out_tokens: int) -> float:
    p = PRICES.get(model)
    if not p:
        return 0.0
    return (in_tokens / 1_000_000) * p["input"] + (out_tokens / 1_000_000) * p["output"]


def claude_complete(
    prompt: str,
    *,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 512,
    system: str | None = None,
) -> LLMResult:
    """One-shot text completion via the Anthropic SDK."""
    from anthropic import Anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing. Add it to .env.")

    client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    in_tok = msg.usage.input_tokens
    out_tok = msg.usage.output_tokens
    return LLMResult(
        text=text,
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=_cost(model, in_tok, out_tok),
    )


def openai_complete(
    prompt: str,
    *,
    model: str = "gpt-4o-mini",
    max_tokens: int = 512,
    system: str | None = None,
) -> LLMResult:
    """One-shot text completion via the OpenAI SDK (Chat Completions)."""
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY missing. Add it to .env.")

    client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
    text = resp.choices[0].message.content or ""
    in_tok = resp.usage.prompt_tokens if resp.usage else 0
    out_tok = resp.usage.completion_tokens if resp.usage else 0
    return LLMResult(
        text=text,
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=_cost(model, in_tok, out_tok),
    )
