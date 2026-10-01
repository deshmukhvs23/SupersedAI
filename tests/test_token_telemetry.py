from dataclasses import asdict, FrozenInstanceError
from types import SimpleNamespace

import pytest

from cppmigrate import llm, patcher, loop
from cppmigrate.evaluate import summarize_records, format_markdown, load_records
from cppmigrate.scanner import Candidate
from cppmigrate.validator import ValidationResult


GOOD = '{"edits":[{"old":"NULL","new":"nullptr"}]}'


def response(content=GOOD, total=29, finish="stop"):
    return llm.LLMResponse(content, "nebius-model", finish, total - 8, 8, total, True)


@pytest.mark.parametrize("mapping", [False, True])
def test_chat_extracts_usage(monkeypatch, mapping):
    payload = {"model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
               "choices": [{"finish_reason": "length", "message": {"content": "hello"}}],
               "usage": {"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29}}
    def objects(value):
        if isinstance(value, dict):
            return SimpleNamespace(**{k: objects(v) for k, v in value.items()})
        if isinstance(value, list):
            return [objects(v) for v in value]
        return value
    raw = payload if mapping else objects(payload)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: raw)))
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    monkeypatch.setenv("NEBIUS_MODEL_FAST", "configured-model")
    result = llm.chat([])
    assert result == llm.LLMResponse("hello", payload["model"], "length", 21, 8, 29, True)


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": "bad", "total_tokens": -1}])
def test_missing_or_invalid_usage(usage):
    result = llm.extract_response({"choices": [], "usage": usage})
    assert result == llm.LLMResponse()


def run_attempts(monkeypatch, tmp_path, responses, retries=1):
    path = tmp_path / "a.cpp"
    path.write_text("int* p = NULL;\n")
    candidate = Candidate("a.cpp", "nullptr", "Replace NULL", [1])
    iterator = iter(responses)
    monkeypatch.setattr(patcher, "chat", lambda *a, **kw: next(iterator))
    monkeypatch.setattr(loop, "validate", lambda *a: ValidationResult(True, "test", ""))
    return loop.migrate_file(tmp_path, candidate, max_retries=retries)


@pytest.mark.parametrize("content,finish,category", [
    (GOOD, "stop", ""),
    ("bad JSON", "stop", "malformed_model_response"),
    ('{"edits":[{"old":"absent","new":"nullptr"}]}', "stop", "no_exact_match"),
    (GOOD, "length", "truncated_model_response"),
])
def test_attempt_telemetry(monkeypatch, tmp_path, content, finish, category):
    result, attempts = run_attempts(monkeypatch, tmp_path, [response(content, finish=finish)])
    attempt = attempts[0]
    assert result.success == (not category)
    assert attempt.failure_category == category
    assert attempt.response_model == "nebius-model"
    assert attempt.finish_reason == finish
    assert (attempt.prompt_tokens, attempt.completion_tokens, attempt.total_tokens) == (21, 8, 29)
    assert attempt.usage_available
    assert (tmp_path / "a.cpp").read_text() == ("int* p = NULL;\n" if category else "int* p = nullptr;\n")


def test_retry_has_independent_usage(monkeypatch, tmp_path):
    first = response("bad", 29)
    result, attempts = run_attempts(monkeypatch, tmp_path, [first, response(total=40)], retries=2)
    assert result.success
    assert [a.model_tier for a in attempts] == ["fast", "strong"]
    assert [a.total_tokens for a in attempts] == [29, 40]
    attempts[1].total_tokens = 100
    assert attempts[0].total_tokens == 29
    assert first.total_tokens == 29
    with pytest.raises(FrozenInstanceError):
        first.total_tokens = 100


def test_legacy_chat(monkeypatch, tmp_path):
    result, attempts = run_attempts(monkeypatch, tmp_path, [GOOD])
    assert result.success
    assert not attempts[0].usage_available
    assert attempts[0].total_tokens is None


def test_legacy_proposal(monkeypatch, tmp_path):
    monkeypatch.setattr(loop, "propose_edits", lambda *a: [{"old": "NULL", "new": "nullptr"}])
    result, attempts = run_attempts(monkeypatch, tmp_path, [])
    assert result.success
    data = asdict(attempts[0])
    assert {k: data[k] for k in llm.LLMResponse().attempt_metadata()} == llm.LLMResponse().attempt_metadata()


def test_validation_failure_keeps_usage(monkeypatch, tmp_path):
    monkeypatch.setattr(loop, "validate", lambda *a: ValidationResult(False, "build", "failed"))
    path = tmp_path / "a.cpp"
    path.write_text("NULL")
    monkeypatch.setattr(patcher, "chat", lambda *a, **kw: response())
    _, attempts = loop.migrate_file(tmp_path, Candidate("a.cpp", "nullptr", "replace", [1]), max_retries=1)
    assert attempts[0].total_tokens == 29
    assert attempts[0].failure_category == "compile_error"
    assert path.read_text() == "NULL"


def test_evaluator_tokens_and_old_jsonl(tmp_path):
    import json
    old = [{"file": "a.cpp", "attempt": 1, "model_tier": "fast", "success": False},
           {"file": "a.cpp", "attempt": 2, "model_tier": "strong", "success": True}]
    path = tmp_path / "old.jsonl"
    path.write_text(''.join(json.dumps(r) + '\n' for r in old))
    assert summarize_records(load_records(path)) == summarize_records(old)
    assert "token_usage" not in summarize_records(old)
    records = [{**r, **response(total=total).attempt_metadata()} for r, total in zip(old, [29, 40])]
    records.append({"file": "b.cpp", "model_tier": "fast", "usage_available": False})
    summary = summarize_records(records)
    usage = summary["token_usage"]
    assert usage == {"prompt_tokens": 53, "completion_tokens": 16, "total_tokens": 69,
                     "avg_total_tokens_per_model_call": 34.5,
                     "total_tokens_per_validated_candidate": 69,
                     "by_model_tier": {"fast": {"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29},
                                       "strong": {"prompt_tokens": 32, "completion_tokens": 8, "total_tokens": 40}},
                     "attempts_with_unavailable_usage": 1, "calls_with_total_tokens": 2}
    assert "| strong | 32 | 8 | 40 |" in format_markdown(path, summary)


def test_truncation_retries_normally(monkeypatch, tmp_path):
    result, attempts = run_attempts(
        monkeypatch, tmp_path, [response(finish="length"), response(total=40)], retries=2
    )
    assert result.success
    assert [a.failure_category for a in attempts] == ["truncated_model_response", ""]
    assert [a.total_tokens for a in attempts] == [29, 40]
    assert [a.model_tier for a in attempts] == ["fast", "strong"]


def test_missing_usage_preserves_response_metadata():
    result = llm.extract_response({
        "model": "nebius-model",
        "choices": [{"message": {"content": GOOD}, "finish_reason": "stop"}],
    })
    assert result.model == "nebius-model"
    assert result.finish_reason == "stop"
    assert result.content == GOOD
    assert not result.usage_available
    assert result.total_tokens is None
    metadata = result.attempt_metadata()
    metadata["response_model"] = "changed"
    assert result.attempt_metadata()["response_model"] == "nebius-model"
