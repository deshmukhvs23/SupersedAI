"""Thin wrapper over an OpenAI-compatible endpoint (Nebius Token Factory).

All endpoint/model names come from env vars so nothing is hard-coded.
`tier="fast"` -> cheap triage/simple edits, `tier="strong"` -> harder refactors.
"""
import os
from openai import OpenAI

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["NEBIUS_API_KEY"],
            base_url=os.environ["NEBIUS_BASE_URL"],
        )
    return _client


def chat(messages: list[dict], tier: str = "fast", temperature: float = 0.0) -> str:
    model = os.environ["NEBIUS_MODEL_STRONG" if tier == "strong" else "NEBIUS_MODEL_FAST"]
    resp = _get_client().chat.completions.create(
        model=model, messages=messages, temperature=temperature
    )
    return resp.choices[0].message.content or ""
