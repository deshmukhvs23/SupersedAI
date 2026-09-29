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
