import argparse
from pathlib import Path

from .loop import run
from .scanner import PATTERNS


def main():
    ap = argparse.ArgumentParser(description="LLM-driven C++ modernization with build/test validation")
    ap.add_argument("repo", type=Path)
    ap.add_argument("--pattern", choices=PATTERNS, default="nullptr")
    ap.add_argument("--limit", type=int, default=10, help="max files to attempt")
    ap.add_argument("--file", dest="target_file", help="only migrate this repository-relative file",)
    ap.add_argument("--out", type=Path, default=Path("results.jsonl"))
    a = ap.parse_args()
    run(a.repo.resolve(), a.pattern, a.limit, a.out, target_file=a.target_file)


if __name__ == "__main__":
    main()
