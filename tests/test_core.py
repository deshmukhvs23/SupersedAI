import pytest
from cppmigrate.patcher import EditError, apply_edits, parse_edits
from cppmigrate.scanner import scan


def test_scan_finds_null(tmp_path):
    (tmp_path / "a.cpp").write_text("int* p = NULL;\nint x;\n")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "skip.cpp").write_text("NULL")
    found = scan(tmp_path, "nullptr")
    assert [c.file for c in found] == ["a.cpp"] and found[0].line_numbers == [1]


def test_apply_edits_exact_match():
    assert apply_edits("int* p = NULL;", [{"old": "NULL", "new": "nullptr"}]) == "int* p = nullptr;"


def test_apply_edits_rejects_ambiguous():
    with pytest.raises(EditError):
        apply_edits("NULL NULL", [{"old": "NULL", "new": "nullptr"}])


def test_parse_edits_strips_fences():
    raw = '```json\n{"edits":[{"old":"a","new":"b"}]}\n```'
    assert parse_edits(raw) == [{"old": "a", "new": "b"}]


def test_scan_finds_simple_typedef(tmp_path):
    source = tmp_path / "types.h"
    source.write_text("typedef unsigned int UserId;\n")

    found = scan(tmp_path, "using")

    assert len(found) == 1
    assert found[0].file == "types.h"
    assert found[0].pattern == "using"
    assert found[0].line_numbers == [1]


def test_migrate_retries_with_strong_model(monkeypatch, tmp_path):
    import cppmigrate.loop as migration_loop
    from cppmigrate.scanner import Candidate
    from cppmigrate.validator import ValidationResult

    source = tmp_path / "a.cpp"
    source.write_text("int* pointer = NULL;\n")

    candidate = Candidate(
        file="a.cpp",
        pattern="nullptr",
        description="Replace NULL with nullptr.",
        line_numbers=[1],
    )

    calls = []

    def fake_propose(source_text, candidate, feedback, tier):
        calls.append((feedback, tier))

        if len(calls) == 1:
            raise EditError("invalid model JSON")

        return [{"old": "NULL", "new": "nullptr"}]

    def fake_validate(repo, build_dir="build"):
        return ValidationResult(
            ok=True,
            stage="test",
            log_tail="",
        )

    monkeypatch.setattr(
        migration_loop,
        "propose_edits",
        fake_propose,
    )
    monkeypatch.setattr(
        migration_loop,
        "validate",
        fake_validate,
    )

    result, attempts = migration_loop.migrate_file(
        tmp_path,
        candidate,
        run_id="unit-run-001",
        repo_revision="abc123",
    )

    assert result.success is True
    assert result.attempts == 2
    assert {
        attempt.run_id
        for attempt in attempts
    } == {"unit-run-001"}
    assert {
        attempt.repo_revision
        for attempt in attempts
    } == {"abc123"}
    assert [attempt.model_tier for attempt in attempts] == [
        "fast",
        "strong",
    ]
    assert attempts[0].stage == "patch"
    assert attempts[0].success is False
    assert attempts[1].success is True
    assert attempts[1].edit_count == 1
    assert source.read_text() == "int* pointer = nullptr;\n"


def test_extract_context_limits_source_window():
    from cppmigrate.patcher import extract_context

    source = "\n".join(
        f"line {number}"
        for number in range(1, 101)
    )

    context = extract_context(
        source,
        line_numbers=[50],
        radius=2,
    )

    assert context.splitlines() == [
        "line 48",
        "line 49",
        "line 50",
        "line 51",
        "line 52",
    ]


def test_migrate_preserves_crlf_line_endings(
    monkeypatch,
    tmp_path,
):
    import cppmigrate.loop as migration_loop
    from cppmigrate.scanner import Candidate
    from cppmigrate.validator import ValidationResult

    source = tmp_path / "windows.cpp"
    source.write_bytes(
        b"int* pointer = NULL;\r\n"
        b"int value = 1;\r\n"
    )

    candidate = Candidate(
        file="windows.cpp",
        pattern="nullptr",
        description="Replace NULL with nullptr.",
        line_numbers=[1],
    )

    monkeypatch.setattr(
        migration_loop,
        "propose_edits",
        lambda source_text, candidate, feedback, tier: [
            {"old": "NULL", "new": "nullptr"}
        ],
    )

    monkeypatch.setattr(
        migration_loop,
        "validate",
        lambda repo, build_dir="build": ValidationResult(
            ok=True,
            stage="test",
            log_tail="",
        ),
    )

    result, attempts = migration_loop.migrate_file(
        tmp_path,
        candidate,
    )

    assert result.success is True
    assert attempts[0].success is True
    assert source.read_bytes() == (
        b"int* pointer = nullptr;\r\n"
        b"int value = 1;\r\n"
    )


def test_apply_multiline_edit_to_crlf_source():
    source = (
        "XMLNode* current = first;\r\n"
        "while (current != NULL) {\r\n"
        "    current = current->next;\r\n"
        "}\r\n"
    )

    edits = [
        {
            "old": (
                "XMLNode* current = first;\n"
                "while (current != NULL) {"
            ),
            "new": (
                "XMLNode* current = first;\n"
                "while (current != nullptr) {"
            ),
        }
    ]

    result = apply_edits(source, edits)

    assert "current != nullptr" in result
    assert result.count("\r\n") == 4
    assert "\n" not in result.replace("\r\n", "")


def test_parse_clang_diagnostics_deduplicates_candidates(
    tmp_path,
):
    from cppmigrate.clang_scanner import (
        parse_clang_diagnostics,
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "main.cpp"

    diagnostic = (
        f"{source}:10:17: warning: use nullptr "
        "[modernize-use-nullptr]\n"
    )

    output = (
        diagnostic
        + diagnostic
        + "/usr/include/header.h:20:4: warning: use nullptr "
        "[modernize-use-nullptr]\n"
    )

    candidates = parse_clang_diagnostics(
        output,
        repo,
        "nullptr",
    )

    assert len(candidates) == 1

    candidate = candidates[0]
    assert candidate.file == "main.cpp"
    assert candidate.line_numbers == [10]
    assert candidate.columns == [17]
    assert candidate.backend == "clang-tidy"
    assert candidate.check == "modernize-use-nullptr"
def test_extract_context_marks_exact_clang_target():
    from cppmigrate.patcher import extract_context

    line = "int len = vsnprintf( 0, 0, format, va );"

    context = extract_context(
        line + "\n",
        line_numbers=[1],
        columns=[22],
        radius=0,
    )

    context_lines = context.splitlines()

    assert context_lines[0] == line
    assert context_lines[1].index("^") == 21
    assert "TARGET line 1, column 22" in context_lines[1]


def test_parse_edits_accepts_one_extra_closing_brace():
    raw = (
        '{"edits":['
        '{"old":"0","new":"nullptr"}'
        ']}}'
    )

    assert parse_edits(raw) == [
        {"old": "0", "new": "nullptr"}
    ]
def test_candidate_metadata_and_failure_taxonomy():
    from cppmigrate.loop import (
        candidate_metadata,
        classify_failure,
    )
    from cppmigrate.scanner import Candidate

    candidate = Candidate(
        file="main.cpp",
        pattern="nullptr",
        description="Use nullptr.",
        line_numbers=[12],
        columns=[24],
        backend="clang-tidy",
        check="modernize-use-nullptr",
    )

    assert candidate_metadata(candidate) == {
        "backend": "clang-tidy",
        "check": "modernize-use-nullptr",
        "line_numbers": [12],
        "columns": [24],
    }

    assert (
        classify_failure(
            "patch",
            "model did not return valid edit JSON",
        )
        == "malformed_model_response"
    )

    assert (
        classify_failure(
            "patch",
            "`old` text must match exactly once, matched 0",
        )
        == "no_exact_match"
    )

    assert (
        classify_failure(
            "build",
            "compiler returned an error",
        )
        == "compile_error"
    )

    assert (
        classify_failure(
            "test",
            "ctest reported a failure",
        )
        == "test_failure"
    )

    assert (
        classify_failure(
            "build",
            "timeout after 900s",
        )
        == "timeout"
    )
def test_apply_edits_uses_clang_target_to_disambiguate():
    from cppmigrate.scanner import Candidate

    source = (
        "_end = 0;\n"
        "int value = 1;\n"
        "_end = 0;\n"
    )

    candidate = Candidate(
        file="main.cpp",
        pattern="nullptr",
        description="Use nullptr.",
        line_numbers=[3],
        columns=[8],
        backend="clang-tidy",
        check="modernize-use-nullptr",
    )

    result = apply_edits(
        source,
        [
            {
                "old": "_end = 0;",
                "new": "_end = nullptr;",
            }
        ],
        candidate=candidate,
    )

    assert result == (
        "_end = 0;\n"
        "int value = 1;\n"
        "_end = nullptr;\n"
    )



@pytest.mark.parametrize("run_id", ["tinyxml2-nullptr-run-02", ""])
def test_run_metadata_records_run_and_revision(
    monkeypatch,
    tmp_path,
    run_id,
):
    import cppmigrate.loop as migration_loop

    monkeypatch.setattr(
        migration_loop,
        "get_repo_revision",
        lambda repo: "8224e42",
    )

    def unexpected_generation():
        pytest.fail("explicit run IDs must not be regenerated")

    monkeypatch.setattr(migration_loop, "generate_run_id", unexpected_generation)

    assert migration_loop.run_metadata(
        tmp_path,
        run_id,
    ) == {
        "run_id": run_id,
        "repo_revision": "8224e42",
    }


def test_run_metadata_generates_utc_identifier(monkeypatch, tmp_path):
    import time
    import uuid
    import cppmigrate.loop as migration_loop

    monkeypatch.setattr(
        migration_loop.time, "gmtime",
        lambda: time.struct_time((2026, 9, 30, 12, 34, 56, 2, 273, 0)),
    )
    monkeypatch.setattr(migration_loop, "get_repo_revision", lambda repo: "abc123")

    monkeypatch.setattr(
        migration_loop.uuid, "uuid4",
        lambda: uuid.UUID("a1b2c3d4-1234-4567-89ab-0123456789ab"),
    )
    assert migration_loop.generate_run_id() == "20260930T123456Z-a1b2c3d4"

    assert migration_loop.run_metadata(tmp_path) == {
        "run_id": "20260930T123456Z-a1b2c3d4",
        "repo_revision": "abc123",
    }


@pytest.mark.parametrize(
    "returncode, stdout, expected",
    [(0, "abc123\n", "abc123"), (0, "\n", "unknown"), (128, "", "unknown")],
)
def test_get_repo_revision(monkeypatch, tmp_path, returncode, stdout, expected):
    import subprocess
    import cppmigrate.loop as migration_loop

    def fake_run(command, **kwargs):
        assert command == ["git", "rev-parse", "--verify", "HEAD"]
        assert kwargs["cwd"] == tmp_path
        return subprocess.CompletedProcess(command, returncode, stdout=stdout)

    monkeypatch.setattr(migration_loop.subprocess, "run", fake_run)
    assert migration_loop.get_repo_revision(tmp_path) == expected


@pytest.mark.parametrize("error", [FileNotFoundError("git"), OSError("unavailable")])
def test_get_repo_revision_handles_unavailable_git(monkeypatch, tmp_path, error):
    import cppmigrate.loop as migration_loop

    def fake_run(*args, **kwargs):
        raise error

    monkeypatch.setattr(migration_loop.subprocess, "run", fake_run)
    assert migration_loop.get_repo_revision(tmp_path) == "unknown"


@pytest.mark.parametrize("run_id", [None, "evaluation-001"])
def test_run_propagates_metadata_to_all_attempts_and_jsonl(monkeypatch, tmp_path, run_id):
    import json
    import cppmigrate.loop as migration_loop
    from cppmigrate.validator import ValidationResult

    for filename in ("a.cpp", "b.cpp"):
        (tmp_path / filename).write_text("int* pointer = NULL;\n")

    metadata_calls = []

    def fake_metadata(repo, supplied_run_id):
        metadata_calls.append((repo, supplied_run_id))
        return {"run_id": supplied_run_id or "20260930T123456Z-a1b2c3d4", "repo_revision": "abc123"}

    monkeypatch.setattr(migration_loop, "run_metadata", fake_metadata)
    monkeypatch.setattr(
        migration_loop, "configure",
        lambda repo, build_dir: ValidationResult(True, "configure", ""),
    )
    monkeypatch.setattr(
        migration_loop, "validate",
        lambda repo, build_dir: ValidationResult(True, "test", ""),
    )

    def fake_propose(source, candidate, feedback, tier):
        # Each candidate independently fails its first patch, then succeeds.
        if tier == "fast":
            raise EditError("model did not return valid edit JSON")
        return [{"old": "NULL", "new": "nullptr"}]

    monkeypatch.setattr(migration_loop, "propose_edits", fake_propose)
    migrate_calls = []
    original_migrate = migration_loop.migrate_file

    def recording_migrate(repo, candidate, **kwargs):
        migrate_calls.append(kwargs)
        return original_migrate(repo, candidate, **kwargs)

    monkeypatch.setattr(migration_loop, "migrate_file", recording_migrate)
    out = tmp_path / "results.jsonl"
    results = migration_loop.run(
        tmp_path, "nullptr", 2, out, build_dir="custom-build", run_id=run_id,
    )

    assert metadata_calls == [(tmp_path, run_id)]
    expected = {"run_id": run_id or "20260930T123456Z-a1b2c3d4", "repo_revision": "abc123"}
    assert migrate_calls == [{"build_dir": "custom-build", **expected}] * 2
    assert len(results) == 2
    assert all(result.success and result.attempts == 2 for result in results)
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(records) == 4
    assert {record["file"] for record in records} == {"a.cpp", "b.cpp"}
    assert [record["success"] for record in records] == [False, True, False, True]
    assert all({key: record[key] for key in expected} == expected for record in records)


@pytest.mark.parametrize("run_id", [None, "cli-evaluation-001"])
def test_cli_passes_optional_run_id(monkeypatch, tmp_path, run_id):
    import sys
    import cppmigrate.cli as cli

    argv = ["cppmigrate", str(tmp_path)]
    if run_id is not None:
        argv.extend(["--run-id", run_id])
    monkeypatch.setattr(sys, "argv", argv)
    calls = []
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    cli.main()

    assert len(calls) == 1
    assert calls[0][0][0] == tmp_path.resolve()
    assert calls[0][1]["run_id"] == run_id
