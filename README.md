# SupersedAI

**A validation-first AI agent for safely modernizing legacy C++ code.**

Verified on 20 candidates across TinyXML-2 and pugixml: 20/20 patches passed build and tests, with 95% first-pass success, supported by 72 offline tests.
Scope: one pattern (`nullptr`), 10 candidates and one run per repository.

LLM agent that modernizes legacy C++ (NVIDIA Nemotron via Nebius Token Factory) and only keeps
a change if the project still **builds and passes its tests**.

Submission: [submission package](SUBMISSION.md) · [three-minute demo script](docs/demo-script.md).

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
    python -m cppmigrate.cli /path/to/pugixml --pattern nullptr --cmake-arg=-DPUGIXML_BUILD_TESTS=ON

Repeat `--cmake-arg` to pass multiple repository-specific CMake configure
arguments. Values beginning with `-` must use the equals form shown above.
SupersedAI checks CTest JSON discovery before running tests and rejects
validation when no tests are registered, or when discovery fails or returns
malformed JSON. Enable the repository's tests through its CMake options.

Each attempt is appended to `results.jsonl` (attempt number, model tier, stage, success, edit count, seconds) to compute the numbers
for your write-up: validated patches / attempted, avg attempts, time per fix.

Every JSONL attempt also records experiment metadata: `run_id` identifies the
evaluation run, and `repo_revision` records the target repository's Git HEAD
before migration (`unknown` when Git metadata is unavailable). All candidates
and retries in one run share these values. The `cmake_args` list records the
extra configure arguments on every attempt (an empty list by default).

When `--run-id` is omitted, the ID combines a UTC timestamp with an eight-character
UUID4 hexadecimal suffix, for example `20260930T123456Z-a1b2c3d4`. The random suffix
reduces collisions between runs started in the same second, but does not guarantee
uniqueness. Supply a unique `--run-id` when your experiment requires that guarantee;
an explicitly supplied ID is preserved unchanged.

Each attempt also records `response_model`, `finish_reason`, `prompt_tokens`,
`completion_tokens`, `total_tokens`, and `usage_available`. Missing usage has
null token counts and `usage_available=false`; calls without a response have
empty model and finish reason. Parsing and exact-match failures retain response
telemetry. A `length` finish reason rejects the proposal before applying edits,
records `truncated_model_response`, and follows normal retry/escalation.

Run `python -m cppmigrate.evaluate results.jsonl` (or add `--json`) to report
observed token totals, totals by model tier, average total tokens per model call
with a reported total, tokens per validated candidate, and unavailable-usage
attempt counts. Totals include failed attempts; missing usage is not estimated,
so incomplete coverage yields partial totals. Older JSONL files retain their
existing summaries. Monetary cost is not estimated without verified pricing.

## Evaluation highlights

Powered by **Nebius Token Factory**, using **NVIDIA Nemotron-3 Nano 30B A3B**
(`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) for fast-model calls and
**NVIDIA Nemotron-3 Super 120B A12B** (`nvidia/nemotron-3-super-120b-a12b`)
for strong-model escalation.

The completed location-aware run `tinyxml2-8224e42-location-aware-limit10-run01`
validated **10/10** of the first 10 `modernize-use-nullptr` candidates in
TinyXML-2's `tinyxml2.cpp`, discovered with `clang-tidy` for the `nullptr`
pattern at revision `8224e427b655b83dae5e2298f1e6919523a78737`.
First-pass success was **90%**, with **10%** escalation: 11 attempts
(1.10 per candidate), 10 fast-model calls, one strong-model call, and one
`no_exact_match` failure. Total time was 192.78 seconds (19.28 seconds average
and 16.18 seconds median per candidate).

The final CMake build and CTest passed; the final source diff contains exactly
10 NULL-pointer-style integer zero replacements with `nullptr`. Candidate
metadata and revision invariants passed. The agent preserved the target's
CRLF line endings; the stored diff was normalized only for repository cleanliness.

Artifacts: [raw attempts](evaluations/raw/tinyxml2-8224e42-location-aware-limit10-run01.jsonl)
and [source diff](evaluations/raw/tinyxml2-8224e42-location-aware-limit10-run01.diff).
This expands the sample but remains limited to one repository, one source file,
one modernization pattern, and one run; it does not establish generalized
production performance.

### First cross-repository benchmark

On 2026-10-01, the pugixml run
`pugixml-27b68329-location-aware-limit10-run01` validated **10/10** of the
first 10 `nullptr` candidates in `src/pugixml.cpp`, using `clang-tidy`'s
`modernize-use-nullptr` check at revision
`27b68329de32cf9c601ca8eb6c588fd639960c40`. The final build and CTest passed,
and all ten changes were manually reviewed as semantic pointer-null replacements.

| Metric | TinyXML-2 (10 candidates) | pugixml (10 candidates) |
|---|---:|---:|
| Validated | 10/10 | 10/10 |
| First-pass success | 90% | 100% |
| Escalation rate | 10% | 0% |
| Total attempts | 11 | 10 |
| Strong-model calls | 1 | 0 |
| Average seconds per candidate | 19.28 | 11.66 |
| Median seconds per candidate | 16.18 | 10.93 |

Combined: **20/20 validated**, **95% first-pass success** (19/20), and
**5% escalation** (1/20), across 21 attempts, 20 fast-model calls, and one
strong-model call. Total time was 309.39 seconds, averaging 15.47 seconds
per candidate.

pugixml artifacts: [raw attempts](evaluations/raw/pugixml-27b68329-location-aware-limit10-run01.jsonl)
and [source diff](evaluations/raw/pugixml-27b68329-location-aware-limit10-run01.diff).
This benchmark covers only two repositories, one modernization pattern,
10 candidates per repository, and one run per repository. Builds and tests
establish regression confidence but do not prove semantic equivalence for all inputs.

### Earlier five-candidate comparison

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
sandboxed validation and ownership-aware
migrations.

## License
MIT
