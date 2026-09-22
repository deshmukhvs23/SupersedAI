"""Core agent loop: propose edit -> apply -> build/test -> feed failures back -> retry."""
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from .patcher import EditError, apply_edits, propose_edits
from .scanner import Candidate, scan
from .validator import configure, validate


@dataclass
class Result:
    file: str
    pattern: str
    success: bool
    attempts: int
    seconds: float
    note: str = ""


def migrate_file(repo: Path, cand: Candidate, max_retries: int = 3) -> Result:
    path = repo / cand.file
    original = path.read_text()
    feedback, t0 = None, time.time()
    for attempt in range(1, max_retries + 1):
        tier = "fast" if attempt == 1 else "strong"  # escalate on failure
        try:
            new = apply_edits(original, propose_edits(original, cand, feedback, tier))
        except EditError as e:
            feedback = str(e)
            continue
        path.write_text(new)
        res = validate(repo)
        if res.ok:
            return Result(cand.file, cand.pattern, True, attempt, time.time() - t0)
        feedback = f"[{res.stage} failed]\n{res.log_tail}"
        path.write_text(original)  # revert before retrying
    return Result(cand.file, cand.pattern, False, max_retries, time.time() - t0, (feedback or "")[:200])


def run(repo: Path, pattern: str, limit: int, out: Path) -> list[Result]:
    if not configure(repo).ok or not validate(repo).ok:
        raise SystemExit("Baseline build/tests fail: pick a repo that passes before changes.")
    results = []
    for cand in scan(repo, pattern)[:limit]:
        r = migrate_file(repo, cand)
        results.append(r)
        print(f"{'OK ' if r.success else 'FAIL'} {r.file} (attempts={r.attempts})")
        with out.open("a") as f:
            f.write(json.dumps(asdict(r)) + "\n")
    ok = sum(r.success for r in results)
    print(f"\n{ok}/{len(results)} patches validated")
    return results
