"""Ask the LLM for edits as exact-match search/replace pairs (more reliable than diffs)."""
import json
import re

from .llm import chat
from .scanner import Candidate

SYSTEM = (
    "You are a careful C++ modernization assistant. "
    "Make the minimal change needed. Never change behavior. "
    "Respond with JSON only, no prose, in the form "
    '{"edits":[{"old":"<exact text from the file>",'
    '"new":"<replacement>"}]}. '
    "Each `old` must appear exactly once in the file, so include "
    "enough real source context to make it unique. "
    "When the context contains a '^ TARGET' marker, modify only "
    "the token directly above that caret. The TARGET marker is an "
    "annotation, not source code; never include it in `old` or `new`. "
    "Only the targeted token should differ between `old` and `new`."
)


class EditError(Exception):
    pass

def extract_context(
    source: str,
    line_numbers: list[int],
    columns: list[int] | None = None,
    radius: int = 12,
) -> str:
    lines = source.splitlines()
    ranges: list[tuple[int, int]] = []

    targets = {
        line_number: column
        for line_number, column in zip(
            line_numbers,
            columns or [],
        )
    }

    for line_number in sorted(set(line_numbers)):
        start = max(0, line_number - radius - 1)
        end = min(len(lines), line_number + radius)

        if ranges and start <= ranges[-1][1]:
            previous_start, previous_end = ranges[-1]
            ranges[-1] = (
                previous_start,
                max(previous_end, end),
            )
        else:
            ranges.append((start, end))

    snippets: list[str] = []

    for start, end in ranges:
        snippet_lines: list[str] = []

        for index in range(start, end):
            line_number = index + 1
            snippet_lines.append(lines[index])

            column = targets.get(line_number)

            if column is not None and column > 0:
                marker = (
                    " " * (column - 1)
                    + f"^ TARGET line {line_number}, "
                    + f"column {column}"
                )
                snippet_lines.append(marker)

        snippets.append("\n".join(snippet_lines))

    return "\n\n... omitted ...\n\n".join(snippets)


def propose_edits(source: str, cand: Candidate, feedback: str | None, tier: str = "fast") -> list[dict]:
    context = extract_context(
        source,
        cand.line_numbers,
	columns = cand.columns,
    )

    user = (
        f"Task: {cand.description}\n"
        f"File: {cand.file}\nLines to look at: {cand.line_numbers}\n\n"
        f"--- RELEVANT CONTEXT START ---\n"
        f"{context}\n"
        f"--- RELEVANT CONTEXT END ---\n"
    )
    if feedback:
        user += f"\nYour previous attempt failed with:\n{feedback}\nFix it.\n"
    raw = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], tier=tier)
    return parse_edits(raw)


def parse_edits(raw: str) -> list[dict]:
    raw = re.sub(
        r"^```(?:json)?|```$",
        "",
        raw.strip(),
        flags=re.M,
    ).strip()

    try:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload, end = json.JSONDecoder().raw_decode(raw)

            # Recover only from one accidental trailing brace.
            if raw[end:].strip() != "}":
                raise

        edits = payload["edits"]

    except (
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as error:
        preview = raw[:200]

        raise EditError(
            "model did not return valid edit JSON: "
            f"{error}; response preview={preview!r}"
        )

    if not isinstance(edits, list) or not edits:
        raise EditError("no edits returned")

    return edits

def match_source_newlines(
    text: str,
    source: str,
) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    if "\r\n" in source:
        return normalized.replace("\n", "\r\n")

    if "\r" in source:
        return normalized.replace("\n", "\r")

    return normalized


def target_offsets(
    source: str,
    candidate: Candidate | None,
) -> list[int]:
    if candidate is None or not candidate.columns:
        return []

    lines = source.splitlines(keepends=True)
    line_starts: list[int] = []
    offset = 0

    for line in lines:
        line_starts.append(offset)
        offset += len(line)

    offsets: list[int] = []

    for line_number, column in zip(
        candidate.line_numbers,
        candidate.columns,
    ):
        if line_number < 1 or line_number > len(lines):
            raise EditError(
                f"target line is outside the file: {line_number}"
            )

        line = lines[line_number - 1].rstrip("\r\n")
        character_index = column - 1

        if character_index < 0 or character_index >= len(line):
            raise EditError(
                "target column is outside the source line: "
                f"line {line_number}, column {column}"
            )

        offsets.append(
            line_starts[line_number - 1] + character_index
        )

    return offsets


def find_match_offsets(source: str, old: str) -> list[int]:
    matches: list[int] = []
    start = 0

    while True:
        match = source.find(old, start)

        if match == -1:
            break

        matches.append(match)
        start = match + 1

    return matches


def apply_edits(
    source: str,
    edits: list[dict],
    candidate: Candidate | None = None,
) -> str:
    for edit in edits:
        old = edit.get("old")
        new = edit.get("new")

        if (
            not isinstance(old, str)
            or not isinstance(new, str)
            or not old
        ):
            raise EditError("malformed edit")

        old = match_source_newlines(old, source)
        new = match_source_newlines(new, source)

        matches = find_match_offsets(source, old)
        targets = target_offsets(source, candidate)

        if targets:
            anchored_matches = [
                match
                for match in matches
                if any(
                    match <= target < match + len(old)
                    for target in targets
                )
            ]

            if len(anchored_matches) != 1:
                raise EditError(
                    "`old` text must match exactly once at target, "
                    f"matched {len(anchored_matches)} at target "
                    f"and {len(matches)} globally: {old[:60]!r}"
                )

            match = anchored_matches[0]

        else:
            if len(matches) != 1:
                raise EditError(
                    "`old` text must match exactly once, "
                    f"matched {len(matches)}: {old[:60]!r}"
                )

            match = matches[0]

        source = (
            source[:match]
            + new
            + source[match + len(old):]
        )

    return source
