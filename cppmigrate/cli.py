import argparse
from pathlib import Path

from .loop import run
from .scanner import PATTERNS


def main():
    ap = argparse.ArgumentParser(description="LLM-driven C++ modernization with build/test validation")
    ap.add_argument("repo", type=Path)
    ap.add_argument("--pattern", choices=PATTERNS, default="nullptr")
    ap.add_argument(
        "--backend",
        choices=("regex", "clang"),
        default="regex",
        help="candidate discovery backend",
    )
    ap.add_argument(
        "--build-dir",
        default="build",
        help="repository-relative CMake build directory",
    )
    ap.add_argument(
        "--cmake-arg",
        action="append",
        default=[],
        help="extra CMake configure argument (repeatable); use --cmake-arg=-DPUGIXML_BUILD_TESTS=ON for values beginning with '-'",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=10,
        help="maximum candidates to attempt",
    )
    ap.add_argument(
        "--file",
        dest="target_file",
        help="only migrate this repository-relative file",
    )
    ap.add_argument("--out", type=Path, default=Path("results.jsonl"))
    ap.add_argument(
        "--run-id",
        help="identifies one evaluation run; generated automatically when omitted",
    )
    a = ap.parse_args()
    run(
        a.repo.resolve(),
        a.pattern,
        a.limit,
        a.out,
        target_file=a.target_file,
        backend=a.backend,
        build_dir=a.build_dir,
        run_id=a.run_id,
        cmake_args=a.cmake_arg,
    )


if __name__ == "__main__":
    main()
