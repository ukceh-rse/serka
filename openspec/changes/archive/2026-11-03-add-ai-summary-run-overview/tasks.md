# Tasks

## 1. Test-mode scenarios (backend)

- [x] 1.1 Add `_mock_insight_retry_run` to `src/serka/routers/mock.py` (insight classify → route → plan → execute → synthesize 1 → evaluate fail `problem: "writing"` → synthesize 2 → evaluate pass → one text message → `accepted` outcome, attempt 2 of 3, with `serka.draft` per synthesize). Verify with a new test in `tests/test_chat_api.py` asserting the step sequence, the first evaluation failing, a single `TEXT_MESSAGE_START` and the outcome.
- [x] 1.2 Add `_mock_refused_run` (classify `inScope: false` with a reason → refuse → refusal text → `refused` outcome). Verify with a test asserting steps are exactly `["classify", "refuse"]` and status `refused`.
- [x] 1.3 Make `mock_stream_fn` choose the run from the request message (`"trend"` → insight, `"weather"` → refused, otherwise keyword). Verify with `uv run pytest tests/test_chat_api.py`: the new tests pass and `test_mock_stream_follows_contract` passes unchanged.

- [x] 1.4 In `agent_event_handler` (`src/serka/chat/events.py`), prefix `Error: ` on tool results whose outcome is not `success`, matching `call_tool`. Verify with a test in `tests/test_chat_events.py` that a tool raising `ModelRetry` yields an `Error: ` result.

## 2. UI test tooling

- [x] 2.1 Add Vitest as a UI dev dependency with an `npm test` script (`vitest run`) using the existing Vite config. Verify that `npm test` runs and exits cleanly from `ui/`.

## 3. Run trace model

- [x] 3.1 Widen `SSEEvent` in `ui/src/api/chat.ts` to the consumed fields (`stepName`, `name`, `value`, `toolCallId`, `toolCallName`, `delta`, `content`, `message`, `models`, plus the `RUN_STARTED`/`RUN_ERROR`/`STEP_*`/`CUSTOM`/`TOOL_CALL_*` types) and drop `THINKING_*`. Make `streamSummary` also stop on `RUN_ERROR`. Verify that `npm run build` type-checks.
- [x] 3.2 Create `ui/src/run/runTrace.ts` with the `RunTrace` types, `emptyRun(now)` and a pure `reduceRun(trace, event, now)` covering steps, `serka.*` custom events, tool call start/args/result, metadata, outcome, `RUN_ERROR` (closing any open step) and synthetic `STREAM_CLOSED`. Verify with `ui/src/run/runTrace.test.ts` replaying event fixtures for: the keyword run, insight with retry, refused, `RUN_ERROR` with a step left open, and early close. Assert statuses, step order and attempts, tool calls attached to the execute step, and that unknown events are ignored.
- [x] 3.3 Show the retry notice in `progressText`, derived from the last two steps per design decision 4: a failed evaluation with attempts remaining. Verify with tests that it is shown on the next stage and gone one stage later.
- [x] 3.4 Add `progressText(trace)`, `summaryText(trace)` and `compactOutcome(trace)` beside the reducer. Verify with tests covering each stage phrase with attempt n of m, the tool name during execute, the retry notice, summary text for accepted / limit_reached / refused (with reason) / error, and `compactOutcome` returning only `{status, path, attemptsUsed, score, models}`.

## 4. Store and stream wiring

- [x] 4.1 In `ui/src/stores/searchStore.ts`, add `aiRun` and `applyAiEvent`. Remove `aiModel`, `aiThinking`, `aiDate` and their setters, and make `resetAiSummary` clear `aiRun`. Verify that `npm run build` passes with no remaining references to the removed fields.
- [x] 4.2 Update `ResultsPage.runSummary`: start a fresh trace, pass every event to `applyAiEvent`, keep `appendAiSummary` for text, apply `RUN_ERROR` with the message on request errors and `STREAM_CLOSED` after the loop, and ignore events once the call is aborted (loading is derived from `aiRun.status`). Verify in test mode (`"weather …"` query and a backend stopped mid-stream) that the spinner always stops.

## 5. Run overview UI

- [x] 5.1 Create `RunOverview` and render it under the AI Summary header: a spinner plus `progressText` while running, and in the same position a status-tinted `summaryText` row with a Details toggle when finished. Remove the provenance chips and `provenanceChipSx`, and widen the panel visibility to include `aiRun`. Verify in test mode that the line morphs in place for the keyword, `"trend …"` and `"weather …"` queries and that no Model/Date chips appear.
- [x] 5.2 Create `RunTimeline`, collapsed by default, with one row per step execution (stage, attempt, result summary, model, duration) and an outcome row. Verify in test mode that the `"trend …"` run shows two synthesize and two evaluate rows with attempt labels and that the first evaluation is shown as failed.
- [x] 5.3 Add nested per-row expanders for raw detail: tool args and results pretty-printed in a height-limited scrollable `pre`, plan steps, draft text and full evaluator feedback. Verify in test mode that the attempt-1 draft is viewable and that the search result JSON scrolls without stretching the panel.
- [x] 5.4 Pass `run: compactOutcome(aiRun)` in the AI Summary `FeedbackWidget` context. Verify in the browser network tab that the feedback request body contains `run` with status, path, attemptsUsed, score and models, and no tool results or drafts.
- [x] 5.5 Document `npm test` and the test-mode scenario keywords (`trend`, `weather`) in `ui/README.md`, and verify the documented commands run as written.

## 6. Integration check

- [x] 6.1 Run `uv run pytest`, `npm test` and `npm run build`, all passing (`npm run lint` cannot run yet; see the known gaps below). Then do a final manual pass in test mode over all three scenarios, checking the progress line, retry notice, settled row styling, timeline, nested detail and feedback payload against `specs/ai-summary-run-overview/spec.md`.
  - Known gap, pre-existing and outside this change: `npm run lint` cannot run because `ui/` has no ESLint config file. After the review fixes, 127 pytest and 17 Vitest tests pass and the build passes. The manual test-mode pass in the browser was done before those fixes.

## Workflow follow-up

- Run `/opsx:verify` against the implementation, then archive the change once reviewed.
