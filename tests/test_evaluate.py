from cppmigrate.evaluate import summarize_records


def test_summarize_records():
    records = [
        {
            "file": "main.cpp",
            "pattern": "nullptr",
            "line_numbers": [10],
            "columns": [5],
            "attempt": 1,
            "model_tier": "fast",
            "success": False,
            "seconds": 2.0,
            "failure_category": "non_unique_match",
        },
        {
            "file": "main.cpp",
            "pattern": "nullptr",
            "line_numbers": [10],
            "columns": [5],
            "attempt": 2,
            "model_tier": "strong",
            "success": True,
            "seconds": 3.0,
            "failure_category": "",
        },
        {
            "file": "main.cpp",
            "pattern": "nullptr",
            "line_numbers": [20],
            "columns": [7],
            "attempt": 1,
            "model_tier": "fast",
            "success": True,
            "seconds": 1.0,
            "failure_category": "",
        },
    ]

    summary = summarize_records(records)

    assert summary["candidates"] == 2
    assert summary["validated"] == 2
    assert summary["success_rate"] == 1.0
    assert summary["first_pass_successes"] == 1
    assert summary["first_pass_rate"] == 0.5
    assert summary["escalated_candidates"] == 1
    assert summary["escalation_rate"] == 0.5
    assert summary["attempts"] == 3
    assert summary["avg_attempts_per_candidate"] == 1.5
    assert summary["total_seconds"] == 6.0
    assert summary["avg_seconds_per_candidate"] == 3.0
    assert summary["median_seconds_per_candidate"] == 3.0
    assert summary["model_calls"] == {
        "fast": 2,
        "strong": 1,
    }
    assert summary["failure_categories"] == {
        "non_unique_match": 1,
    }


def test_summarize_metadata_enriched_jsonl(tmp_path):
    import json
    from cppmigrate.evaluate import load_records

    records = [
        {
            "file": "main.cpp", "pattern": "nullptr", "attempt": 1,
            "model_tier": "fast", "success": False, "seconds": 2.0,
            "failure_category": "compile_error",
        },
        {
            "file": "main.cpp", "pattern": "nullptr", "attempt": 2,
            "model_tier": "strong", "success": True, "seconds": 3.0,
        },
    ]
    enriched = [
        {**record, "run_id": "tinyxml2-nullptr-run-02", "repo_revision": "8224e42"}
        for record in records
    ]
    path = tmp_path / "results.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in enriched))

    summary = summarize_records(load_records(path))

    assert summary == summarize_records(records)
    assert summary["candidates"] == 1
    assert summary["validated"] == 1
    assert summary["attempts"] == 2
    assert summary["first_pass_rate"] == 0.0
    assert summary["total_seconds"] == 5.0
    assert summary["model_calls"] == {"fast": 1, "strong": 1}
    assert summary["failure_categories"] == {"compile_error": 1}
