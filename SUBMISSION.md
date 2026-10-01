# SupersedAI

**SupersedAI modernizes legacy C++ one validated patch at a time, making the build and tests the gatekeepers of AI-generated changes.**

A validation-first AI agent for safely modernizing legacy C++.

Verified on 20 candidates across TinyXML-2 and pugixml: 20/20 patches passed build and tests, with 95% first-pass success, supported by 72 offline tests.
Scope: one pattern (`nullptr`), 10 candidates and one run per repository.

[Repository](https://github.com/deshmukhvs23/SupersedAI) · MIT license · [Demo script](docs/demo-script.md)

## Problem and intended users

Maintainers of legacy C++ libraries and applications need to modernize code without introducing regressions. Repeated idioms are easy to find, but a proposed replacement still needs appropriate source context, precise placement, and validation. SupersedAI is intended for C++ maintainers and teams who can build their projects with CMake and exercise them through CTest.

## How it works

Deterministic tools discover candidates and enforce patch, build, and test gates; the model supplies probabilistic edit proposals.

1. Discover candidates with clang-tidy or regex.
2. Supply bounded, location-anchored source context to NVIDIA Nemotron through the Nebius Token Factory / Nebius AI Cloud OpenAI-compatible endpoint.
3. Request an exact-match edit proposal and apply it with location-aware matching.
4. Build with CMake, discover registered tests with CTest, reject repositories with zero registered tests, and execute the tests.
5. On failure, retry with failure feedback and escalate from Nano to Super. Roll back after final failure.
6. Record attempts, outcomes, timings, and available token usage in JSONL.

## Architecture and components

I implemented the Python agent orchestration, Clang-guided candidate pipeline, location-aware patch application, retry and model-escalation policy, CMake/CTest validation gates, rollback behavior, telemetry, and reproducible evaluation harness. clang-tidy supplies semantic diagnostics, while Nebius Token Factory hosts the NVIDIA models used for edit proposals.

| Component | Responsibility |
|---|---|
| CLI and discovery | Select repository, pattern, candidate scope, and clang-tidy or regex backend |
| Prompt and model client | Bound source context around the candidate; request Nemotron edits through the OpenAI client |
| Patcher | Apply exact-match edits using candidate locations |
| Validation loop | CMake build, CTest discovery and execution, failure feedback, retry, escalation, rollback |
| Metrics and evaluation | Store JSONL attempt records and summarize results and available token usage |

## Built With

- Python and the OpenAI Python client.
- **Nebius Token Factory / Nebius AI Cloud** OpenAI-compatible endpoint for model inference.
- **NVIDIA Nemotron-3 Nano 30B A3B**, fast model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.
- **NVIDIA Nemotron-3 Super 120B A12B**, strong model: `nvidia/nemotron-3-super-120b-a12b`.
- clang-tidy, regex discovery, CMake, CTest, pytest, and JSONL metrics.

## Why AI helps beyond search-and-replace

Plain search-and-replace cannot reliably distinguish a pointer-null expression from an unrelated integer zero. Candidate discovery and bounded source context give the model information for proposing a context-sensitive edit. The model can also revise a proposal using failure feedback. For the evaluated `nullptr` pattern, clang-tidy already offers useful modernization support; this benchmark does not establish that AI outperforms clang-tidy fixes. The agent's broader value is the proposal, feedback, validation, and rollback workflow.

## Safety and validation design

An AI proposal is not accepted solely because it looks plausible. Exact-match and location-aware application constrain where it can land; CMake and CTest determine whether the changed project builds and passes its registered tests. Zero registered tests cause rejection. Failed attempts supply feedback for retry and stronger-model escalation, with rollback after final failure. JSONL records and stored diffs make outcomes reviewable. All stored diffs were manually reviewed.

Local execution is not sandboxed. Builds and tests reduce regression risk but do not prove full semantic equivalence.

## Verified evaluation

The benchmark evaluated `nullptr`, with 10 candidates per repository and one benchmark run per repository.

| Metric | Verified result |
|---|---:|
| Offline tests | 72 |
| Repositories | 2: TinyXML-2 and pugixml |
| Validated patches | 20/20 |
| First-pass success | 95% (19/20) |
| Escalation rate | 5% (1/20) |
| Total attempts | 21 |
| Fast-model calls | 20 |
| Strong-model calls | 1 |
| Total time | 309.39 seconds |
| Average time per candidate | 15.47 seconds |

| Repository | Exact evaluated revision | Validated candidates |
|---|---|---:|
| TinyXML-2 | `8224e427b655b83dae5e2298f1e6919523a78737` | 10/10 |
| pugixml | `27b68329de32cf9c601ca8eb6c588fd639960c40` | 10/10 |

Exact revisions, raw JSONL records, and diffs are committed. See the [evaluation report](evaluations/README.md), [TinyXML-2 records](evaluations/raw/tinyxml2-8224e42-location-aware-limit10-run01.jsonl), [TinyXML-2 diff](evaluations/raw/tinyxml2-8224e42-location-aware-limit10-run01.diff), [pugixml records](evaluations/raw/pugixml-27b68329-location-aware-limit10-run01.jsonl), and [pugixml diff](evaluations/raw/pugixml-27b68329-location-aware-limit10-run01.diff).

### Separate token telemetry smoke test

Token telemetry was added after the stored 20-candidate benchmarks. The following is a smoke test, not part of that benchmark, and does not establish benchmark token totals.

| Field | Provider-reported value |
|---|---|
| Model | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| Prompt tokens | 473 |
| Completion tokens | 2206 |
| Total tokens | 2679 |
| finish_reason | `stop` |

Provider-reported completion usage dominated this call. These counters alone do not establish how much was visible output or hidden reasoning. No monetary cost is calculated or claimed.

## Limitations

- Two repositories, one evaluated modernization pattern (`nullptr`), 10 evaluated candidates per repository, and one benchmark run per repository are a small sample.
- Local execution is not sandboxed.
- Build/tests reduce regression risk but do not prove full semantic equivalence; results depend on the target's tests.
- Model output can be malformed or fail exact matching, requiring retry and escalation.
- Token telemetry was added after the stored 20-candidate benchmarks; the separate smoke test cannot fill that gap.
- These results do not establish generalized production performance or repeatable latency gains.

## Future roadmap

Proposed next steps are repeated evaluations across more repositories and modernization patterns, sandboxed validation, ownership-aware migrations, stronger structured-output handling, and clearer token-usage reporting. These are future work, not claims about the evaluated system.

## Nebius and NVIDIA feedback

**Use and onboarding.** Nebius Token Factory supplied inference for both NVIDIA Nemotron models through its OpenAI-compatible endpoint. The verified onboarding sequence from zero to the first successful API call was: configure the OpenAI client with the Nebius base URL, API key, and model identifiers; attempt a call; receive an initial HTTP 401 because the copied key was incomplete at 14 characters; correct the copy to use the complete key; make a successful API call. This account does not assume additional console steps or elapsed onboarding time.

**What worked well.** OpenAI-client compatibility let the agent use the standard Python client with the Nebius endpoint and switch model identifiers for escalation. Nano succeeded first-pass on 19/20 benchmark candidates. The benchmark’s single initial failure was categorized as `no_exact_match`; the Super model corrected that proposal on retry. The retry loop used failure feedback to obtain a corrected proposal; this was an application-level workflow using the two hosted models.

**What could improve.** Structured JSON occasionally contained malformed output or an extra brace. Model-generated surrounding context also caused exact-match failures when that text did not exist in the source. More reliable schema-conforming edit responses, examples emphasizing verbatim source spans, and clearer documentation of structured-output behavior would help. Authentication guidance emphasizing complete key copying would make the observed 401 easier to diagnose.

Token-accounting and pricing clarity are another improvement area: document precisely what provider-reported completion usage includes and how usage maps to applicable pricing. The separate smoke call reported 473 prompt tokens and 2206 completion tokens; completion usage dominated, but we cannot attribute all of it to visible output or hidden reasoning. We make no monetary-cost claim.

**Would we build with it again?** Yes: OpenAI-client compatibility and the observed Nano-to-Super recovery make the platform a useful foundation for this validation-first workflow. We would retain external build/test validation and expand evaluation before making broader reliability claims.
