"""Core agent loop: propose edit -> apply -> build/test -> feed failures back -> retry."""
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path

from .clang_scanner import scan_clang
from .patcher import EditError, apply_edits, propose_edits
from .scanner import Candidate, scan
from .validator import configure, validate


@dataclass
class AttemptResult:
    file: str
    pattern: str
    attempt: int
    model_tier: str
    success: bool
    stage: str
    seconds: float
    edit_count: int = 0
    note: str = ""
    backend: str = "regex"
    check: str = ""
    line_numbers: list[int] = field(default_factory=list)
    columns: list[int] = field(default_factory=list)
    failure_category: str = ""
    run_id: str = ""
    repo_revision: str = "unknown"
    cmake_args: list[str] = field(default_factory=list)


@dataclass
class Result:
    file: str
    pattern: str
    success: bool
    attempts: int
    seconds: float
    note: str = ""


def read_source(path: Path) -> str:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as source_file:
        return source_file.read()

def candidate_metadata(cand: Candidate) -> dict:
    return {
        "backend": cand.backend,
        "check": cand.check,
        "line_numbers": list(cand.line_numbers),
        "columns": list(cand.columns),
    }

def get_repo_revision(repo: Path) -> str:
    try:
        process = subprocess.run(
            [
                "git",
                "rev-parse",
                "--verify",
                "HEAD",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"

    if process.returncode != 0:
        return "unknown"

    return process.stdout.strip() or "unknown"


def generate_run_id() -> str:
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def run_metadata(
    repo: Path,
    run_id: str | None = None,
) -> dict:
    if run_id is None:
        run_id = generate_run_id()

    return {
        "run_id": run_id,
        "repo_revision": get_repo_revision(repo),
    }

def classify_failure(stage: str, message: str) -> str:
    if "timeout after" in message:
        return "timeout"

    if stage == "patch":
        if "valid edit JSON" in message:
            return "malformed_model_response"

        if "matched 0" in message:
            return "no_exact_match"

        if "must match exactly once" in message:
            return "non_unique_match"

        if "malformed edit" in message:
            return "malformed_edit"

        if "no edits returned" in message:
            return "no_edits"

        return "patch_error"

    if stage == "build":
        return "compile_error"

    if stage == "test":
        return "test_failure"

    return f"{stage}_failure"


def write_source(path: Path, content: str) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as source_file:
        source_file.write(content)

def migrate_file(
    repo: Path,
    cand: Candidate,
    max_retries: int = 3,
    build_dir: str = "build",
    run_id: str = "",
    repo_revision: str = "unknown",
    cmake_args: list[str] | None = None,
) -> tuple[Result, list[AttemptResult]]:
    path = repo / cand.file
    original = read_source(path)
    feedback = None
    migration_start = time.time()
    attempt_results: list[AttemptResult] = []
    cmake_args = list(cmake_args or [])

    def attempt_metadata() -> dict:
        return {
            **candidate_metadata(cand),
            "run_id": run_id,
            "repo_revision": repo_revision,
            "cmake_args": list(cmake_args),
        }

    for attempt in range(1, max_retries + 1):
        attempt_start = time.time()
        tier = "fast" if attempt == 1 else "strong"

        try:
            edits = propose_edits(
                original,
                cand,
                feedback,
                tier,
            )
            new_source = apply_edits(original, edits, candidate=cand,)

        except EditError as error:
            feedback = str(error)

            attempt_results.append(
                AttemptResult(
                    file=cand.file,
                    pattern=cand.pattern,
                    attempt=attempt,
                    model_tier=tier,
                    success=False,
                    stage="patch",
                    seconds=time.time() - attempt_start,
                    note=feedback[:200],
                    failure_category=classify_failure(
                        "patch",
                        feedback,
                    ),
                    **attempt_metadata(),
                )
            )
            continue

        write_source(path, new_source)
        validation = validate(repo, build_dir)

        if validation.ok:
            attempt_results.append(
                AttemptResult(
                    file=cand.file,
                    pattern=cand.pattern,
                    attempt=attempt,
                    model_tier=tier,
                    success=True,
                    stage="test",
                    seconds=time.time() - attempt_start,
                    edit_count=len(edits),
                    **attempt_metadata(),
                )
            )

            result = Result(
                file=cand.file,
                pattern=cand.pattern,
                success=True,
                attempts=attempt,
                seconds=time.time() - migration_start,
            )
            return result, attempt_results

        feedback = (
            f"[{validation.stage} failed]\n"
            f"{validation.log_tail}"
        )

        attempt_results.append(
            AttemptResult(
                file=cand.file,
                pattern=cand.pattern,
                attempt=attempt,
                model_tier=tier,
                success=False,
                stage=validation.stage,
                seconds=time.time() - attempt_start,
                edit_count=len(edits),
                note=feedback[:200],
                failure_category=classify_failure(
                    validation.stage,
                    validation.log_tail,
                ),
                **attempt_metadata(),
            )
        )

        write_source(path, original)

    result = Result(
        file=cand.file,
        pattern=cand.pattern,
        success=False,
        attempts=max_retries,
        seconds=time.time() - migration_start,
        note=(feedback or "")[:200],
    )
    return result, attempt_results


def run(
    repo: Path,
    pattern: str,
    limit: int,
    out: Path,
    target_file: str | None = None,
    backend: str = "regex",
    build_dir: str = "build",
    run_id: str | None = None,
    cmake_args: list[str] | None = None,
) -> list[Result]:
    cmake_args = list(cmake_args or [])
    metadata = run_metadata(repo, run_id)
    baseline = configure(repo, build_dir, cmake_args=cmake_args)
    if baseline.ok:
        baseline = validate(repo, build_dir)
    if not baseline.ok:
        raise SystemExit(
            f"Baseline {baseline.stage} failed: {baseline.log_tail}\n"
            "Pick a repo that passes before changes. "
            "If no tests are registered, enable repository tests with a "
            "repository-specific CMake option via --cmake-arg=-DNAME=VALUE."
        )

    results: list[Result] = []

    if backend == "regex":
        candidates = scan(repo, pattern)
    elif backend == "clang":
        candidates = scan_clang(repo, pattern, build_dir)
    else:
        raise ValueError(
            f"Unsupported scanner backend: {backend}"
        )

    if target_file is not None:
        candidates = [
            candidate
            for candidate in candidates
            if candidate.file == target_file
        ]

        if not candidates:
            raise SystemExit(
                f"No {pattern!r} candidate found in "
                f"{target_file!r}."
            )

    for candidate in candidates[:limit]:
        result, attempt_results = migrate_file(
            repo,
            candidate,
            build_dir=build_dir,
            cmake_args=cmake_args,
            **metadata,
        )
        results.append(result)

        print(
            f"{'OK ' if result.success else 'FAIL'} "
            f"{result.file} "
            f"(attempts={result.attempts})"
        )

        with out.open("a") as output_file:
            for attempt_result in attempt_results:
                output_file.write(
                    json.dumps(asdict(attempt_result)) + "\n"
                )

    successful = sum(result.success for result in results)

    print(
        f"\n{successful}/{len(results)} "
        "patches validated"
    )
    return results
