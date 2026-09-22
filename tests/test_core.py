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
