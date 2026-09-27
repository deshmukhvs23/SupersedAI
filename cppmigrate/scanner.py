"""Find modernization candidates. Deterministic on purpose: cheap, testable."""
import re
from dataclasses import dataclass, field
from pathlib import Path

CPP_EXT = {".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh"}
SKIP_DIRS = {"build", ".git", "third_party", "external", "vendor", "node_modules"}

# pattern name -> (regex, human description for the LLM prompt)
PATTERNS = {
    "nullptr": (re.compile(r"\bNULL\b"), "Replace the NULL macro with nullptr."),
    "using": (
        re.compile(r"^\s*typedef\s+.+\s+\w+\s*;", re.M),
        "Replace simple typedef declarations with `using Name = Type;` aliases.",
    ),
}


@dataclass
class Candidate:
    file: str
    pattern: str
    description: str
    line_numbers: list[int] = field(default_factory=list)
    columns: list[int] = field(default_factory=list)
    backend: str = "regex"
    check: str = ""


def scan(repo: Path, pattern: str) -> list[Candidate]:
    rx, desc = PATTERNS[pattern]
    out: list[Candidate] = []
    for p in sorted(repo.rglob("*")):
        if p.suffix not in CPP_EXT or any(part in SKIP_DIRS for part in p.parts):
            continue
        try:
            lines = p.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        hits = [i + 1 for i, line in enumerate(lines) if rx.search(line)]
        if hits:
            out.append(Candidate(str(p.relative_to(repo)), pattern, desc, hits))
    return out
