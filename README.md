# cpp-migrate-agent

LLM agent that modernizes legacy C++ (NVIDIA Nemotron via Nebius Token Factory) and only keeps
a change if the project still **builds and passes its tests**.

## Loop
scan (deterministic) -> LLM proposes exact-match edits -> apply -> cmake build -> ctest
-> on failure feed the log back, escalate to the stronger model, retry (max 3) -> revert if still failing.

## Setup
    pip install -r requirements.txt
    cp .env.example .env   # then fill the values from Nebius
    set -a; source .env; set +a
    pytest                 # offline tests, no API needed

## Run
    python -m cppmigrate.cli /path/to/cmake-repo --pattern nullptr --limit 10
    python -m cppmigrate.cli /path/to/cmake-repo --pattern nullptr --file src/file.cpp --limit 1

Each attempt is appended to `results.jsonl` (attempt number, model tier, stage, success, edit count, seconds) to compute the numbers
for your write-up: validated patches / attempted, avg attempts, time per fix.

## Status
MVP: patterns `nullptr`, `using`, retry logging, rollback, targeted file selection, bounded prompt context, newline preservation, and evaluation metrics. Next: Clang-based candidates, sandbox runner, more patterns, eval on 2-3 repos.

## License
MIT
