import json
import subprocess
import sys

import pytest

from cppmigrate import cli, validator


@pytest.mark.parametrize("args", [[], ["-DPUGIXML_BUILD_TESTS=ON", "-DCMAKE_BUILD_TYPE=Debug"]])
def test_cli_cmake_arguments(monkeypatch, tmp_path, args):
    monkeypatch.setattr(sys, "argv", ["cppmigrate", str(tmp_path)] + [
        f"--cmake-arg={arg}" for arg in args
    ])
    calls = []
    monkeypatch.setattr(cli, "run", lambda *a, **kw: calls.append(kw))
    cli.main()
    assert calls[0]["cmake_args"] == args


@pytest.mark.parametrize("args", [None, [], ["-DPUGIXML_BUILD_TESTS=ON", "-DVALUE=with spaces"]])
def test_configure_command(monkeypatch, tmp_path, args):
    def fake_run(command, **kwargs):
        assert command == [
            "cmake", "-S", ".", "-B", "custom-build",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", *(args or []),
        ]
        assert kwargs["cwd"] == tmp_path
        assert not kwargs.get("shell", False)
        return subprocess.CompletedProcess(command, 0, stdout="configured", stderr="")

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    if args is None:
        result = validator.configure(tmp_path, "custom-build")
    else:
        result = validator.configure(tmp_path, "custom-build", cmake_args=args)
    assert result == validator.ValidationResult(True, "configure", "configured")


@pytest.mark.parametrize("count", [1, 2, 300])
def test_validate_discovers_tests_before_running_ctest(monkeypatch, tmp_path, count):
    commands = []
    payload = json.dumps({"tests": [{"name": f"test-{i}"} for i in range(count)]})

    def fake_run(command, **kwargs):
        commands.append(command)
        assert kwargs["cwd"] == tmp_path
        assert not kwargs.get("shell", False)
        # stderr must not corrupt the JSON, and large JSON must not be truncated.
        stdout = payload if "--show-only=json-v1" in command else "passed"
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="warning")

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    result = validator.validate(tmp_path, "custom-build")
    assert result.ok and result.stage == "test"
    assert commands == [
        ["cmake", "--build", "custom-build", "-j"],
        ["ctest", "--test-dir", "custom-build", "--show-only=json-v1"],
        ["ctest", "--test-dir", "custom-build", "--output-on-failure"],
    ]


@pytest.mark.parametrize("payload, message", [
    ('{"tests": []}', "No tests are registered"),
    ('not json', "Invalid CTest discovery JSON"),
    ('null', "Invalid CTest discovery JSON"),
    ('{}', "Invalid CTest discovery JSON"),
    ('{"tests": {}}', "Invalid CTest discovery JSON"),
    ('{"tests": [null]}', "Invalid CTest discovery JSON"),
    ('{"tests": [{}]}', "Invalid CTest discovery JSON"),
])
def test_validate_rejects_empty_or_invalid_discovery(monkeypatch, tmp_path, payload, message):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    result = validator.validate(tmp_path)
    assert not result.ok
    assert result.stage == "test_discovery"
    assert message in result.log_tail
    assert len(commands) == 2


@pytest.mark.parametrize("failure", ["exit", "timeout", "missing"])
def test_validate_fails_safely_on_discovery_failure(monkeypatch, tmp_path, failure):
    def fake_run(command, **kwargs):
        if command[0] == "cmake":
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        assert "--show-only=json-v1" in command
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 900)
        if failure == "missing":
            raise FileNotFoundError("ctest unavailable")
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="discovery error")

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    result = validator.validate(tmp_path)
    assert not result.ok and result.stage == "test_discovery"
    assert result.log_tail


def test_validate_build_failure_skips_discovery(monkeypatch, tmp_path):
    monkeypatch.setattr(validator, "run", lambda *a: (1, "build failed"))
    monkeypatch.setattr(validator, "discover_tests", lambda *a: pytest.fail("build failed"))
    assert validator.validate(tmp_path) == validator.ValidationResult(False, "build", "build failed")


def test_validate_preserves_ctest_failure(monkeypatch, tmp_path):
    responses = iter([(0, ""), (8, "test failed")])
    monkeypatch.setattr(validator, "run", lambda *a: next(responses))
    monkeypatch.setattr(validator, "discover_tests", lambda *a: validator.ValidationResult(True, "test_discovery", ""))
    assert validator.validate(tmp_path) == validator.ValidationResult(False, "test", "test failed")


def test_validate_handles_discovery_decoding_failure(monkeypatch, tmp_path):
    def fake_run(command, **kwargs):
        if command[0] == "cmake":
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        assert "--show-only=json-v1" in command
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(validator.subprocess, "run", fake_run)
    result = validator.validate(tmp_path)
    assert not result.ok
    assert result.stage == "test_discovery"
    assert "discovery output could not be decoded" in result.log_tail


@pytest.mark.parametrize("args", [None, ["-DPUGIXML_BUILD_TESTS=ON"]])
def test_migration_records_arguments_on_validation_failure(monkeypatch, tmp_path, args):
    from cppmigrate import loop
    from cppmigrate.scanner import scan

    source = tmp_path / "a.cpp"
    source.write_text("int* p = NULL;\n")
    candidate = scan(tmp_path, "nullptr")[0]
    monkeypatch.setattr(loop, "propose_edits", lambda *a: [{"old": "NULL", "new": "nullptr"}])
    monkeypatch.setattr(loop, "validate", lambda *a: validator.ValidationResult(
        False, "test_discovery", "No tests are registered",
    ))
    result, attempts = loop.migrate_file(tmp_path, candidate, cmake_args=args)
    assert not result.success
    assert len(attempts) == 3
    assert all(attempt.cmake_args == (args or []) for attempt in attempts)
    assert all(attempt.stage == "test_discovery" for attempt in attempts)
    assert source.read_text() == "int* p = NULL;\n"
