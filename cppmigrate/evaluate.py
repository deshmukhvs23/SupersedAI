"""Summarize attempt-level SupersedAI evaluation records."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


def candidate_key(record: dict) -> tuple:
    return (
        record.get("file", ""),
        record.get("pattern", ""),
        tuple(record.get("line_numbers") or []),
        tuple(record.get("columns") or []),
    )


def summarize_records(records: list[dict]) -> dict:
    grouped: dict[tuple, list[dict]] = defaultdict(list)

    for record in records:
        grouped[candidate_key(record)].append(record)

    for attempts in grouped.values():
        attempts.sort(
            key=lambda record: record.get("attempt", 0)
        )

    candidates = len(grouped)
    validated = sum(
        any(record.get("success") for record in attempts)
        for attempts in grouped.values()
    )

    first_pass_successes = sum(
        bool(attempts and attempts[0].get("success"))
        for attempts in grouped.values()
    )

    escalated_candidates = sum(
        any(
            record.get("model_tier") == "strong"
            for record in attempts
        )
        for attempts in grouped.values()
    )

    total_seconds = sum(
        float(record.get("seconds", 0.0))
        for record in records
    )

    candidate_seconds = [
        sum(
            float(record.get("seconds", 0.0))
            for record in attempts
        )
        for attempts in grouped.values()
    ]

    model_calls = Counter(
        record.get("model_tier", "unknown")
        for record in records
    )

    failure_categories = Counter(
        record.get("failure_category")
        for record in records
        if (
            not record.get("success")
            and record.get("failure_category")
        )
    )

    summary = {
        "candidates": candidates,
        "validated": validated,
        "success_rate": (
            validated / candidates
            if candidates
            else 0.0
        ),
        "first_pass_successes": first_pass_successes,
        "first_pass_rate": (
            first_pass_successes / candidates
            if candidates
            else 0.0
        ),
        "escalated_candidates": escalated_candidates,
        "escalation_rate": (
            escalated_candidates / candidates
            if candidates
            else 0.0
        ),
        "attempts": len(records),
        "avg_attempts_per_candidate": (
            len(records) / candidates
            if candidates
            else 0.0
        ),
        "total_seconds": total_seconds,
        "avg_seconds_per_candidate": (
            total_seconds / candidates
            if candidates
            else 0.0
        ),
        "median_seconds_per_candidate": (
            median(candidate_seconds)
            if candidate_seconds
            else 0.0
        ),
        "model_calls": dict(sorted(model_calls.items())),
        "failure_categories": dict(
            sorted(failure_categories.items())
        ),
    }

    # Preserve the old summary shape for records predating telemetry.
    if any("usage_available" in record for record in records):
        fields = ("prompt_tokens", "completion_tokens", "total_tokens")
        available = [record for record in records if record.get("usage_available")]
        totals = {name: sum(record.get(name) or 0 for record in available) for name in fields}
        tiers = {}
        for tier in sorted(model_calls):
            tiers[tier] = {
                name: sum(record.get(name) or 0 for record in available
                          if record.get("model_tier", "unknown") == tier)
                for name in fields
            }
        total_calls = sum(record.get("total_tokens") is not None for record in available)
        summary["token_usage"] = {
            **totals,
            "avg_total_tokens_per_model_call": totals["total_tokens"] / total_calls if total_calls else None,
            "total_tokens_per_validated_candidate": totals["total_tokens"] / validated if validated and total_calls else None,
            "by_model_tier": tiers,
            "attempts_with_unavailable_usage": len(records) - len(available),
            "calls_with_total_tokens": total_calls,
        }
    return summary


def load_records(path: Path) -> list[dict]:
    records: list[dict] = []

    for line_number, line in enumerate(
        path.read_text().splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON: {error}"
            ) from error

    return records


def format_markdown(path: Path, summary: dict) -> str:
    lines = [
        f"# Evaluation: {path.name}",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Candidates | {summary['candidates']} |",
        f"| Validated | {summary['validated']} |",
        f"| Success rate | {summary['success_rate']:.1%} |",
        (
            "| First-pass success rate | "
            f"{summary['first_pass_rate']:.1%} |"
        ),
        (
            "| Escalation rate | "
            f"{summary['escalation_rate']:.1%} |"
        ),
        f"| Total attempts | {summary['attempts']} |",
        (
            "| Average attempts/candidate | "
            f"{summary['avg_attempts_per_candidate']:.2f} |"
        ),
        f"| Total seconds | {summary['total_seconds']:.2f} |",
        (
            "| Average seconds/candidate | "
            f"{summary['avg_seconds_per_candidate']:.2f} |"
        ),
        (
            "| Median seconds/candidate | "
            f"{summary['median_seconds_per_candidate']:.2f} |"
        ),
        "",
        "## Model calls",
        "",
    ]

    for model, count in summary["model_calls"].items():
        lines.append(f"- `{model}`: {count}")

    lines.extend(
        [
            "",
            "## Failure categories",
            "",
        ]
    )

    if summary["failure_categories"]:
        for category, count in (
            summary["failure_categories"].items()
        ):
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- None")

    if "token_usage" in summary:
        usage = summary["token_usage"]
        lines.extend(["", "## Token usage", "", "Observed totals; averages use calls with reported total tokens.", ""])
        for name in ("prompt_tokens", "completion_tokens", "total_tokens",
                     "avg_total_tokens_per_model_call", "total_tokens_per_validated_candidate",
                     "attempts_with_unavailable_usage", "calls_with_total_tokens"):
            lines.append(f"- {name}: {usage[name]}")
        lines.extend(["", "| Model tier | Prompt tokens | Completion tokens | Total tokens |",
                      "|---|---:|---:|---:|"])
        for tier, totals in usage["by_model_tier"].items():
            lines.append(f"| {tier} | {totals['prompt_tokens']} | {totals['completion_tokens']} | {totals['total_tokens']} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize SupersedAI JSONL results"
    )
    parser.add_argument("results", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON",
    )
    args = parser.parse_args()

    summary = summarize_records(
        load_records(args.results)
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_markdown(args.results, summary))


if __name__ == "__main__":
    main()
