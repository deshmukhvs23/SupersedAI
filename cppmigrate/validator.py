"""Build + test a repo. Swap `run` for a sandbox call (e.g. Token Factory Sandboxes) later."""
import json
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


def configure(
    repo: Path,
    build_dir: str = "build",
    cmake_args: list[str] | None = None,
) -> ValidationResult:
    code, log = run(
        [
            "cmake",
            "-S",
            ".",
            "-B",
            build_dir,
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
            *(cmake_args or []),
        ],
        repo,
    )
    return ValidationResult(code == 0, "configure", log)


def discover_tests(repo: Path, build_dir: str = "build") -> ValidationResult:
    command = ["ctest", "--test-dir", build_dir, "--show-only=json-v1"]
    try:
        process = subprocess.run(
            command, cwd=repo, capture_output=True, text=True, timeout=900,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(False, "test_discovery", "CTest discovery timeout after 900s")
    except UnicodeError as error:
        return ValidationResult(
            False, "test_discovery",
            f"CTest discovery output could not be decoded: {error}",
        )
    except OSError as error:
        return ValidationResult(False, "test_discovery", f"CTest discovery failed: {error}")

    if process.returncode != 0:
        return ValidationResult(
            False, "test_discovery",
            f"CTest discovery failed (exit {process.returncode}): "
            + (process.stdout + process.stderr)[-4000:],
        )

    # Discovery needs complete stdout; the usual log-tail truncation would
    # corrupt JSON for repositories with many tests. Keep stderr separate.
    try:
        discovery = json.loads(process.stdout)
    except (ValueError, RecursionError) as error:
        return ValidationResult(False, "test_discovery", f"Invalid CTest discovery JSON: {error}")
    if (
        not isinstance(discovery, dict)
        or not isinstance(discovery.get("tests"), list)
        or any(
            not isinstance(test, dict)
            or not isinstance(test.get("name"), str)
            or not test["name"]
            for test in discovery["tests"]
        )
    ):
        return ValidationResult(False, "test_discovery", "Invalid CTest discovery JSON: expected a tests list of named tests")
    if not discovery["tests"]:
        return ValidationResult(False, "test_discovery", "No tests are registered with CTest; enable repository tests with CMake arguments.")
    return ValidationResult(True, "test_discovery", "")


def validate(repo: Path, build_dir: str = "build") -> ValidationResult:
    code, log = run(["cmake", "--build", build_dir, "-j"], repo)
    if code != 0:
        return ValidationResult(False, "build", log)
    discovery = discover_tests(repo, build_dir)
    if not discovery.ok:
        return discovery
    code, log = run(["ctest", "--test-dir", build_dir, "--output-on-failure"], repo)
    return ValidationResult(code == 0, "test", log)
