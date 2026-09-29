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

Each attempt is appended to `results.jsonl` (attempt number, model tier, stage, success, edit count, seconds) to compute the numbers
for your write-up: validated patches / attempted, avg attempts, time per fix.

## Status
MVP: regex and clang-tidy discovery, patterns `nullptr` and `using`, exact-match edits, model escalation, rollback, target-anchored prompts, newline preservation, and per-attempt metrics. Next: full-repository evaluation, failure taxonomy, sandboxed validation, and harder ownership-aware migrations.

## License
MIT
