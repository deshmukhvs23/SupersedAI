import json
import re
import subprocess
from pathlib import Path

from .scanner import Candidate


CLANG_CHECKS = {
    "nullptr": (
        "modernize-use-nullptr",
        "Replace the semantic null pointer with nullptr.",
    ),
    "using": (
        "modernize-use-using",
        "Replace the typedef declaration with a using alias.",
    ),
}

DIAGNOSTIC = re.compile(
    r"^(.+?):(\d+):(\d+): warning: .* \[([^\]]+)\]$"
)


def get_compiled_files(
    repo: Path,
    build_dir: Path,
) -> list[Path]:
    database = build_dir / "compile_commands.json"

    if not database.exists():
        raise RuntimeError(
            f"Compilation database not found: {database}. "
            "Configure CMake with "
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON."
        )

    entries = json.loads(database.read_text())

    return sorted(
        {
            Path(entry["file"]).resolve()
            for entry in entries
            if Path(entry["file"]).suffix
            in {".cpp", ".cc", ".cxx"}
        }
    )


def parse_clang_diagnostics(
    output: str,
    repo: Path,
    pattern: str,
) -> list[Candidate]:
    check, description = CLANG_CHECKS[pattern]
    repo = repo.resolve()
    candidates: dict[tuple[str, int, int], Candidate] = {}

    for output_line in output.splitlines():
        match = DIAGNOSTIC.match(output_line)

        if not match:
            continue

        filename, line, column, reported_check = match.groups()

        if reported_check != check:
            continue

        absolute_file = Path(filename).resolve()

        try:
            relative_file = absolute_file.relative_to(repo)
        except ValueError:
            continue

        key = (
            str(relative_file),
            int(line),
            int(column),
        )

        candidates[key] = Candidate(
            file=str(relative_file),
            pattern=pattern,
            description=description,
            line_numbers=[int(line)],
            columns=[int(column)],
            backend="clang-tidy",
            check=check,
        )

    return [
        candidates[key]
        for key in sorted(candidates)
    ]


def scan_clang(
    repo: Path,
    pattern: str,
    build_dir: str = "build",
    timeout: int = 900,
) -> list[Candidate]:
    repo = repo.resolve()
    build_path = (repo / build_dir).resolve()
    check, _ = CLANG_CHECKS[pattern]
    compiled_files = get_compiled_files(repo, build_path)

    command = [
        "clang-tidy",
        "-p",
        str(build_path),
        f"-checks=-*,{check}",
        *[str(path) for path in compiled_files],
    ]

    process = subprocess.run(
        command,
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    output = process.stdout + process.stderr
    candidates = parse_clang_diagnostics(
        output,
        repo,
        pattern,
    )

    if process.returncode != 0 and not candidates:
        raise RuntimeError(
            "clang-tidy failed:\n"
            + output[-4000:]
        )

    return candidates
