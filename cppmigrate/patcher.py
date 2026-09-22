"""Ask the LLM for edits as exact-match search/replace pairs (more reliable than diffs)."""
import json
import re

from .llm import chat
from .scanner import Candidate

SYSTEM = (
    "You are a careful C++ modernization assistant. Make the minimal change needed. "
    "Never change behavior. Respond with JSON only, no prose, in the form "
    '{"edits":[{"old":"<exact text from the file>","new":"<replacement>"}]}. '
    "Each `old` must appear exactly once in the file, so include enough surrounding context."
)


class EditError(Exception):
    pass


def propose_edits(source: str, cand: Candidate, feedback: str | None, tier: str = "fast") -> list[dict]:
    user = (
        f"Task: {cand.description}\n"
        f"File: {cand.file}\nLines to look at: {cand.line_numbers}\n\n"
        f"--- FILE START ---\n{source}\n--- FILE END ---\n"
    )
    if feedback:
        user += f"\nYour previous attempt failed with:\n{feedback}\nFix it.\n"
    raw = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], tier=tier)
    return parse_edits(raw)


def parse_edits(raw: str) -> list[dict]:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        edits = json.loads(raw)["edits"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise EditError(f"model did not return valid edit JSON: {e}")
    if not isinstance(edits, list) or not edits:
        raise EditError("no edits returned")
    return edits


def apply_edits(source: str, edits: list[dict]) -> str:
    for e in edits:
        old, new = e.get("old"), e.get("new")
        if not isinstance(old, str) or not isinstance(new, str) or not old:
            raise EditError("malformed edit")
        if source.count(old) != 1:
            raise EditError(f"`old` text must match exactly once, matched {source.count(old)}: {old[:60]!r}")
        source = source.replace(old, new)
    return source
