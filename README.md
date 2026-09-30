# SupersedAI

**A validation-first AI agent for safely modernizing legacy C++ code.**

LLM agent that modernizes legacy C++ (NVIDIA Nemotron via Nebius Token Factory) and only keeps
a change if the project still **builds and passes its tests**.

## Loop
scan (regex or clang-tidy) -> LLM proposes exact-match edits -> apply -> cmake build -> ctest
-> on failure feed the log back, escalate to the stronger model, retry (max 3) -> revert if still failing.

## Setup
    pip install -r requirements.txt
    cp .env.example .env   # then fill the values from Nebius
    set -a; source .env; set +a
    pytest                 # offline tests, no API needed

## Run
    python -m cppmigrate.cli /path/to/cmake-repo --pattern nullptr --limit 10
    python -m cppmigrate.cli /path/to/cmake-repo --pattern nullptr --backend clang --build-dir build --limit 10
    python -m cppmigrate.cli /path/to/cmake-repo --pattern nullptr --file src/file.cpp --limit 1
    python -m cppmigrate.cli /path/to/tinyxml2 --pattern nullptr --run-id tinyxml2-nullptr-run-02

Each attempt is appended to `results.jsonl` (attempt number, model tier, stage, success, edit count, seconds) to compute the numbers
for your write-up: validated patches / attempted, avg attempts, time per fix.

Every JSONL attempt also records experiment metadata: `run_id` identifies the
evaluation run, and `repo_revision` records the target repository's Git HEAD
before migration (`unknown` when Git metadata is unavailable). All candidates
and retries in one run share these values.

When `--run-id` is omitted, the ID combines a UTC timestamp with an eight-character
UUID4 hexadecimal suffix, for example `20260930T123456Z-a1b2c3d4`. The random suffix
reduces collisions between runs started in the same second, but does not guarantee
uniqueness. Supply a unique `--run-id` when your experiment requires that guarantee;
an explicitly supplied ID is preserved unchanged.

## Evaluation

On the first five `clang-tidy` `modernize-use-nullptr` candidates from
TinyXML-2 revision `8224e42`, both patching strategies validated all five
changes through CMake and CTest.

| Metric | Global matching | Location-aware |
|---|---:|---:|
| First-pass success | 20% | 80% |
| Escalation rate | 80% | 20% |
| Total attempts | 10 | 6 |
| Strong-model calls | 5 | 1 |
| Non-unique-match failures | 4 | 0 |

Location-aware matching eliminated ambiguous global matches and reduced total
attempts by 40%. Latency did not improve in this small run because of two slow
model responses, so more repetitions are required.

See [the complete evaluation report](evaluations/README.md) for methodology,
latency results, limitations, raw JSONL records, and source diffs.

## Status
MVP: regex and clang-tidy discovery, `nullptr` and `using` patterns,
target-anchored prompts, location-aware patch application, model escalation,
rollback, failure taxonomy, newline preservation, JSONL metrics, and a
reproducible evaluation summarizer. Next: repeated full-repository evaluation,
sandboxed validation, token/cost instrumentation, and ownership-aware
migrations.

## License
MIT
