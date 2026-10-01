"""Thin wrapper over an OpenAI-compatible endpoint (Nebius Token Factory).

All endpoint/model names come from env vars so nothing is hard-coded.
`tier="fast"` -> cheap triage/simple edits, `tier="strong"` -> harder refactors.
"""
import os
from dataclasses import dataclass
from openai import OpenAI

@dataclass(frozen=True)
class LLMResponse:
    content: str = ""
    model: str = ""
    finish_reason: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    usage_available: bool = False

    def attempt_metadata(self) -> dict:
        return {
            "response_model": self.model,
            "finish_reason": self.finish_reason,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "usage_available": self.usage_available,
        }


def normalize_response(response: LLMResponse | str) -> LLMResponse:
    return response if isinstance(response, LLMResponse) else LLMResponse(content=response)


def extract_response(response) -> LLMResponse:
    def get(value, name, default=None):
        return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)

    choices = get(response, "choices", []) or []
    choice = choices[0] if choices else None
    usage = get(response, "usage")

    def tokens(name):
        value = get(usage, name)
        return value if type(value) is int and value >= 0 else None

    prompt = tokens("prompt_tokens")
    completion = tokens("completion_tokens")
    total = tokens("total_tokens")
    return LLMResponse(
        content=get(get(choice, "message"), "content") or "",
        model=get(response, "model") or "",
        finish_reason=get(choice, "finish_reason") or "",
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        usage_available=any(value is not None for value in (prompt, completion, total)),
    )


_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["NEBIUS_API_KEY"],
            base_url=os.environ["NEBIUS_BASE_URL"],
        )
    return _client


def chat(messages: list[dict], tier: str = "fast", temperature: float = 0.0) -> LLMResponse:
    model = os.environ["NEBIUS_MODEL_STRONG" if tier == "strong" else "NEBIUS_MODEL_FAST"]
    resp = _get_client().chat.completions.create(
        model=model, messages=messages, temperature=temperature
    )
    return extract_response(resp)
