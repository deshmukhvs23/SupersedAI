# cpp-migrate-agent

LLM agent that modernizes legacy C++ (NVIDIA Nemotron via Nebius Token Factory) and only keeps
a change if the project still **builds and passes its tests**.

## Loop
scan (deterministic) -> LLM proposes exact-match edits -> apply -> cmake build -> ctest
-> on failure feed the log back, escalate to the stronger model, retry (max 3) -> revert if still failing.

## Setup
    pip install -r requirements.txt
    cp .env.example .env   # fill values from the Token Factory docs, then: export $(cat .env | xargs)
    pytest                 # offline tests, no API needed

## Run
    python -m cppmigrate.cli /path/to/cmake-repo --pattern nullptr --limit 10

Each attempt is appended to `results.jsonl` (success, attempts, seconds) to compute the numbers
for your write-up: validated patches / attempted, avg attempts, time per fix.

## Status
MVP: patterns `nullptr`, `using`. Next: Clang-based candidates, sandbox runner, more patterns, eval on 2-3 repos.

## License
Add a LICENSE file (e.g. MIT) before submitting; the hackathon requires one.
