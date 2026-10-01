# SupersedAI: three-minute demo

Run commands from the SupersedAI repository root in a prepared environment. This is a demonstration, not an installation walkthrough. Have credentials loaded privately and a disposable, clean pugixml checkout ready at `/tmp/supersedai-demo-pugixml`, at revision `27b68329de32cf9c601ca8eb6c588fd639960c40`. The live candidate is a new demonstration, separate from the committed benchmark.

**API-key safety:** never display `.env`, print credentials or environment variables, enable shell tracing, or show a key in terminal history. Keep credential loading and any authentication troubleshooting off camera. Local execution is not sandboxed; use the prepared disposable checkout.

## 0:00–0:25 — Legacy C++ problem

**Screen:** README title, then the committed pugixml diff.

```bash
sed -n '1,60p' evaluations/raw/pugixml-27b68329-location-aware-limit10-run01.diff
```

**Narration:** “Legacy C++ has repeated modernization opportunities, but maintainers need confidence that each change belongs in the right place and preserves tested behavior. Replacing every zero blindly is unsafe: some represent null pointers, and others are ordinary numbers. SupersedAI makes the build and tests the gatekeepers of AI-generated changes.”

## 0:25–0:50 — SupersedAI solution

**Screen:** SUBMISSION.md workflow; highlight proposal, validation, retry, and rollback.

**Narration:** “SupersedAI discovers candidates with clang-tidy or regex, sends bounded source context to Nemotron, and applies an exact-match proposal using candidate locations. It builds with CMake, discovers CTest tests, rejects zero-test repositories, and runs the tests. Failure triggers feedback, retry, and stronger-model escalation. Final failure triggers rollback.”

## 0:50–1:20 — Architecture and Nebius/NVIDIA tools

**Screen:** SUBMISSION.md architecture and Built With sections, with both exact model IDs visible.

**Narration:** “Nebius Token Factory supplies inference through the Nebius AI Cloud OpenAI-compatible endpoint. NVIDIA Nemotron-3 Nano 30B A3B proposes edits; NVIDIA Nemotron-3 Super 120B A12B handles escalation. The Python agent controls bounded context, location-aware patching, CMake and CTest validation, rollback, and JSONL metrics with available token usage.”

## 1:20–2:05 — Live demonstration

**Screen:** terminal showing the prepared target revision, one-candidate run, diff, and evaluation summary. Start the API call promptly.

```bash
git -C /tmp/supersedai-demo-pugixml rev-parse HEAD
python -m cppmigrate.cli /tmp/supersedai-demo-pugixml \
  --pattern nullptr --backend clang --file src/pugixml.cpp --limit 1 \
  --cmake-arg=-DPUGIXML_BUILD_TESTS=ON \
  --cmake-arg=-DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  --out /tmp/supersedai-demo-attempts.jsonl --run-id supersedai-demo-recording
git -C /tmp/supersedai-demo-pugixml diff -- src/pugixml.cpp
python -m cppmigrate.evaluate /tmp/supersedai-demo-attempts.jsonl
```

**Narration:** “This disposable checkout is at the recorded pugixml revision. I am asking for one nullptr candidate. The agent proposes and applies the edit, then requires the build and registered tests to pass. The diff shows what changed, and the summary reports attempts and validation outcomes. This live demonstration is separate from the stored benchmark.”

**Delivery:** speak the first two sentences while the call runs. Continue with the diff and summary narration only when those outputs are visible; otherwise use the backup narration in place of the remaining live narration.

**Backup if the API is slow:** at approximately 1:40, switch to a second prepared terminal and show committed artifacts. Do not claim the live call completed; do not wait past this segment. Inspect its outcome after recording.

```bash
python -m cppmigrate.evaluate evaluations/raw/pugixml-27b68329-location-aware-limit10-run01.jsonl
sed -n '1,60p' evaluations/raw/pugixml-27b68329-location-aware-limit10-run01.diff
python -m cppmigrate.evaluate evaluations/raw/tinyxml2-8224e42-location-aware-limit10-run01.jsonl
```

**Backup narration:** “The live API is taking longer than this recording allows. These are committed records and reviewed diffs from the verified runs. They show the completed validation results; they are not output from today's live call.”

## 2:05–2:35 — Verified results

**Screen:** SUBMISSION.md verified evaluation table and revision table.

**Narration:** “Across two repositories, TinyXML-2 and pugixml, all twenty of twenty patches validated, with 95 percent first-pass success, supported by 72 offline tests. This small sample covers one pattern, ten candidates and one run per repository. All stored diffs were reviewed. Builds and tests reduce regression risk; they do not prove full semantic equivalence.”

## 2:35–2:55 — Platform and model feedback

**Screen:** feedback section and both exact API identifiers from Built With; keep identifiers visible rather than reading them aloud.

**Narration:** “Nebius Token Factory made OpenAI-compatible onboarding straightforward after correcting an incomplete key copy. NVIDIA Nemotron-3 Nano 30B A3B handled first-pass proposals; NVIDIA Nemotron-3 Super 120B A12B handled retries. More reliable structured output would help. I would build with the platform again.”

## 2:55–3:00 — Closing line

**Screen:** SupersedAI title and `https://github.com/deshmukhvs23/SupersedAI`.

**Narration:** “SupersedAI: modernize legacy C++, one validated patch at a time.”

## Recording checklist

- Rehearse the narration to fit the timestamps; keep tables readable and terminal text large.
- Prepare the environment and clang-tidy/CMake/CTest prerequisites before recording; do not show installation steps.
- Verify the disposable checkout revision and clean status before the take. Use a fresh checkout and unused output path for another take, so appended metrics cannot mix recordings.
- Load credentials privately; close credential files, disable shell tracing, and hide notifications.
- Prepare SUBMISSION.md, both committed summaries, and the pugixml diff in advance for the backup terminal.
- Label live results separately from the benchmark; never imply guaranteed live latency or success.
- Keep the token smoke test separate: 473 prompt, 2206 completion, 2679 total, `stop`, Nano. Provider-reported completion usage dominated; do not label it all visible output or hidden reasoning, or claim monetary cost.
- State that local execution is not sandboxed and that validation does not prove full semantic equivalence.
- End at three minutes with the repository URL visible.
