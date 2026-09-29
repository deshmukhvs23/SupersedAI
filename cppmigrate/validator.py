"""Build + test a repo. Swap `run` for a sandbox call (e.g. Token Factory Sandboxes) later."""
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationResult:
    ok: bool
    stage: str
    log_tail: str


def run(cmd: list[str], cwd: Path, timeout: int = 900) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s: {' '.join(cmd)}"
    return p.returncode, (p.stdout + p.stderr)[-4000:]


def configure(repo: Path, build_dir: str = "build") -> ValidationResult:
    code, log = run(
        [
            "cmake",
            "-S",
            ".",
            "-B",
            build_dir,
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ],
        repo,
    )
    return ValidationResult(code == 0, "configure", log)


def validate(repo: Path, build_dir: str = "build") -> ValidationResult:
    code, log = run(["cmake", "--build", build_dir, "-j"], repo)
    if code != 0:
        return ValidationResult(False, "build", log)
    code, log = run(["ctest", "--test-dir", build_dir, "--output-on-failure"], repo)
    return ValidationResult(code == 0, "test", log)
