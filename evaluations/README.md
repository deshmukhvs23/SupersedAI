# SupersedAI Evaluation

## Experiment

- Date: 2026-09-29
- Target project: TinyXML-2
- Target revision: `8224e42`
- Pattern: `nullptr`
- Discovery backend: `clang-tidy`
- Check: `modernize-use-nullptr`
- Scope: first five candidates in `tinyxml2.cpp`
- Fast model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
- Strong model: `nvidia/nemotron-3-super-120b-a12b`
- Validation: CMake build followed by CTest
- Retry limit: three attempts per candidate

The experiment compares global exact-match patch application with
Clang-location-aware patch application. Both variants began from the same
TinyXML-2 revision and processed the same five semantic candidates.

## Results

| Metric | Global matching | Location-aware |
|---|---:|---:|
| Validated patches | 5/5 | 5/5 |
| Success rate | 100% | 100% |
| First-pass success rate | 20% | 80% |
| Escalation rate | 80% | 20% |
| Total attempts | 10 | 6 |
| Average attempts per candidate | 2.00 | 1.20 |
| Fast-model calls | 5 | 5 |
| Strong-model calls | 5 | 1 |
| Non-unique-match failures | 4 | 0 |
| No-exact-match failures | 1 | 1 |
| Average seconds per candidate | 15.13 | 23.42 |
| Median seconds per candidate | 15.85 | 17.15 |

## Interpretation

Location-aware matching eliminated all four non-unique-match failures. It
increased first-pass success from 20% to 80%, reduced total attempts by 40%,
and reduced strong-model calls from five to one.

Latency did not improve in this run. The location-aware run contained fast
model calls of approximately 30 and 45 seconds, so average time increased
despite fewer attempts. More repeated runs are required before drawing a
latency conclusion.

One no-exact-match failure remained because the fast model produced source
text that did not exist in the file. The strong model corrected that attempt.

This is a small five-candidate experiment. It demonstrates the effect of the
patch-location change but is not yet evidence of repository-wide performance.

## Reproduce the summaries

```bash
python -m cppmigrate.evaluate \
  evaluations/raw/tinyxml2-8224e42-nullptr-limit5.jsonl

python -m cppmigrate.evaluate \
  evaluations/raw/tinyxml2-8224e42-location-aware-limit5.jsonl
```

The corresponding raw JSONL records are stored in
`evaluations/raw/`.
