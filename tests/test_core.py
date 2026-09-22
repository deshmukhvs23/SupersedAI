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

    def fake_validate(repo):
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
    )

    assert result.success is True
    assert result.attempts == 2
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
        lambda repo: ValidationResult(
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
