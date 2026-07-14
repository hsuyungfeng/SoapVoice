---
phase: 15-audio-cpp
plan: 01
subsystem: asr
tags: [audio.cpp, asr, integration]

# Dependency graph
requires:
  - phase: v1.0
    provides: [baseline WhisperModel and GUI architecture]
provides:
  - AudioCppModel wrapper for audio.cpp server
  - filter_hallucinations utility extracted from WhisperModel
  - ASRFactory updated to support audiocpp backend
affects: [gui, packaging]

# Tech tracking
tech-stack:
  added: [requests]
  patterns: [adapter pattern for ASR engines, centralized utility for hallucination filtering]

key-files:
  created:
    - src/asr/utils.py
    - src/asr/audiocpp_model.py
  modified:
    - src/asr/whisper_model.py
    - src/asr/asr_factory.py
    - tests/test_asr.py

key-decisions:
  - "Extract hallucination filtering logic from WhisperModel into a centralized src/asr/utils.py to ensure identical output quality between engines."
  - "Implement AudioCppModel using requests.post to communicate with the local audiocpp_server, with automatic segmentation reconstruction when filtering hallucinations."

patterns-established:
  - "Centralized hallucination filtering function applied across different ASR backends."

requirements-completed: [PERF-01]

# Metrics
duration: 4min
completed: 2026-07-14
---

# Phase 15 Plan 01: AudioCpp Wrapper and Factory Update Summary

**AudioCppModel HTTP wrapper with centralized hallucination filtering and factory integration**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-14T15:59:49+08:00
- **Completed:** 2026-07-14T16:03:00+08:00
- **Tasks:** 4
- **Files modified:** 5 (3 modified, 2 created)

## Accomplishments
- Extracted and centralized hallucination filtering logic into `src/asr/utils.py`
- Implemented `AudioCppModel` to transcribe audio via HTTP calls to a local `audiocpp_server`
- Updated `ASRBackendFactory` to support the new `audiocpp` engine, retaining traditional Chinese conversion
- Added full unit test coverage for `AudioCppModel` and factory integration

## Task Commits

Each task was committed atomically:

1. **Task 1: extract filter_hallucinations into utils.py** - `647fb18` (feat)
2. **Tasks 2-4: implement AudioCppModel and update ASR factory** - `1025550` (feat)

**Plan metadata:** (To be committed)

## Files Created/Modified
- `src/asr/utils.py` - Extracted `filter_hallucinations` function.
- `src/asr/whisper_model.py` - Refactored to import and use the centralized filtering logic.
- `src/asr/audiocpp_model.py` - Created the `AudioCppModel` HTTP wrapper.
- `src/asr/asr_factory.py` - Added `AUDIOCPP` enum and instantiation logic.
- `tests/test_asr.py` - Added tests for `AudioCppModel.transcribe()` and factory loading.

## Decisions Made
- `filter_hallucinations` was designed to process text on a per-segment basis inside `AudioCppModel` and correctly reconstruct the final output, mirroring `WhisperModel` behavior.
- Use `requests.post` instead of local subprocess calls inside `AudioCppModel` to allow for server pooling / daemonized API performance improvements.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- **Test execution missing mocked fixture:** the `mocker` fixture from `pytest-mock` was not installed in the current environment. 
  - **Resolution:** Replaced the `mocker` usage with standard library `unittest.mock.Mock` and pytest's native `monkeypatch` fixture. Tests passed successfully.
- **Hallucination filter logic interaction with HTTP payload:** During tests, applying `filter_hallucinations` blindly on the whole text concatenated string filtered out the entire text due to a single match.
  - **Resolution:** Fixed `audiocpp_model.py` to filter per-segment and recombine `filtered_text` iteratively (similar to `WhisperModel`).

## Next Phase Readiness
- ASR engine backend wrapper is fully implemented and tested.
- Ready for GUI integration (adding engine dropdown options in ConfigManager and desktop app) in the next plan.

---
*Phase: 15-audio-cpp*
*Completed: 2026-07-14*
