"""Core agent loop: propose edit -> apply -> build/test -> feed failures back -> retry."""
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

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


@dataclass
class Result:
    file: str
    pattern: str
    success: bool
    attempts: int
    seconds: float
    note: str = ""


def migrate_file(
    repo: Path,
    cand: Candidate,
    max_retries: int = 3,
) -> tuple[Result, list[AttemptResult]]:
    path = repo / cand.file
    original = path.read_text()
    feedback = None
    migration_start = time.time()
    attempt_results: list[AttemptResult] = []

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
            new_source = apply_edits(original, edits)

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
                )
            )
            continue

        path.write_text(new_source)
        validation = validate(repo)

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
            )
        )

        path.write_text(original)

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
) -> list[Result]:
    if not configure(repo).ok or not validate(repo).ok:
        raise SystemExit(
            "Baseline build/tests fail: "
            "pick a repo that passes before changes."
        )

    results: list[Result] = []

    for candidate in scan(repo, pattern)[:limit]:
        result, attempt_results = migrate_file(repo, candidate)
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

