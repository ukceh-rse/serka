# Design

## Context

See proposal.md for motivation and `specs/ai-summary-run-overview/spec.md` for required behaviour.

Current state relevant to the approach:

- `ResultsPage.runSummary` calls `streamSummary` (`ui/src/api/chat.ts`), which parses `data:` lines and calls back per event. The loop ends only on `RUN_FINISHED`. The handler updates `searchStore` fields: `aiSummary`, `aiModel`, `aiDate`, `aiThinking` and `aiLoading`.
- `AISummary.tsx` reads those fields. It returns `null` unless it is loading or has text, so a run that errors with no text currently shows nothing.
- What the event stream guarantees (from `chat-agent-events` and `src/serka/chat/events.py`):
  - `serka.step` always follows `STEP_STARTED`.
  - A stage that raises gets **no** `STEP_FINISHED`, and the run then ends with `RUN_ERROR`.
  - Each tool call is `START`, then `ARGS` (one or more deltas), then `END`, then `RESULT`, all sharing one `toolCallId`. The `RESULT` content is a JSON string, or `Error: …` on failure.
  - `RUN_METADATA` is a raw SSE event whose payload is in its `data:` line, so the existing parser already picks it up.
  - Evaluation `score` is an integer from 1 to 5. A refused run has `score: null` and `attemptsUsed: 0`.
- For `insight` runs, the answer text arrives in one block after the final evaluate. For `keyword` runs it streams during synthesize, and evaluate runs after it.
- The UI has no test runner today. Test mode (`src/serka/routers/mock.py`) replays one scripted keyword run.

## Goals / Non-Goals

**Goals:**
- One place that turns the event stream into a run model, which the progress line, summary row, timeline and feedback all read from.
- That run model can be tested without a browser or backend.

**Non-Goals:**
- Reusing any of this on the Chat page now. Nothing should prevent it later, but no work is done for it.
- Persisting traces, or showing traces for past searches.
- Interpreting tool results per tool (for example "12 datasets found"). Results are shown as pretty-printed JSON.

## Decisions

### 1. A pure reducer builds a `RunTrace` from events

`reduceRun(trace: RunTrace, event: SSEEvent, now: number): RunTrace` lives in a new `ui/src/run/runTrace.ts` with no React or store imports. `RunTrace` holds:

- `status`: `running | accepted | limit_reached | refused | error`, plus an optional `error` message
- `path`, `models`, `startedAt`, `finishedAt`
- `steps[]`: one entry per stage execution, holding `name`, `attempt`, `maxAttempts`, `model`, `startedAt`, `finishedAt?`, the optional stage results `classification`, `plan`, `draft` and `evaluation`, and `toolCalls[]` (`id`, `name`, `args`, `result?`, `ok?`)
- `outcome?`: the `serka.outcome` value

Custom events and tool calls attach to the **last open step**. `now` is passed in, not read from the clock, so tests are deterministic. Durations come from client receipt times.

*Alternatives:* deriving the views straight from a raw event list on every render would leave interpretation logic spread across components. Putting handling into the existing store setters would be hard to test. A reducer gives one tested interpretation of the contract.

### 2. Store holds the trace; the chips' store fields go

`searchStore` gains `aiRun: RunTrace | null` and a `applyAiEvent(event)` action that runs the reducer. When the reducer returns the same trace (text deltas, events after the run ends), the action returns the unchanged state so subscribers are not notified. `aiModel`, `aiThinking`, `aiLoading` and their setters are removed: loading is `aiRun?.status === 'running'`. `aiDate` is replaced by `aiRun.finishedAt`. `aiSummary` text stays separate: it is answer content, and markdown rendering and link extraction already depend on it. `resetAiSummary` clears `aiRun`.

### 3. Stream termination becomes explicit

`streamSummary` and `streamChat` break on `RUN_FINISHED` **or** `RUN_ERROR`. If the request itself fails, `ResultsPage` applies a `RUN_ERROR` carrying the error's message. After the loop it applies a synthetic `{type: 'STREAM_CLOSED'}` event, and the reducer turns a still-`running` trace into `error`. Once a call's `AbortController` is aborted (a newer run superseded it, or the page unmounted), that call applies nothing more, so it cannot clobber the current run. When the page unmounts with a run still going, the summary is reset so revisiting the search starts a fresh run. `SSEEvent` is widened to the event types and fields actually consumed. The dead `THINKING_*` types are dropped.

*Alternative:* a timeout. That was rejected because the stream closing is already a reliable signal.

### 4. Progress text and summary row are pure functions of the trace

`progressText(trace)` and `summaryText(trace)` live next to the reducer, so wording is unit-tested and the components stay thin. The stage-to-phrase mapping:

| Stage | Phrase |
|---|---|
| classify | Understanding your question |
| route | Choosing an approach |
| plan | Planning the search |
| execute | Searching the catalogue (plus the current tool name) |
| synthesize | Writing the answer (attempt n of m) |
| evaluate | Checking the answer (attempt n of m) |
| refuse | Out of scope |

The attempt ("attempt n of m") is shown when the run allows more than one attempt, for `synthesize` and `evaluate`, and for any stage whose attempt is above 1. `showsAttempt(step)` holds this rule for both the progress line and the timeline labels.

The retry notice ("Attempt 1 didn't pass: *feedback*, retrying") is not stored. `progressText` derives it: if either of the last two steps carries a failed evaluation with attempts remaining, the notice replaces the stage phrase. It therefore stays visible through the stage after the failed evaluation and clears when the next one starts, without a timer. Timers in the reducer would break purity.

### 5. Component layout (morph in place)

`AISummary` renders a new `RunOverview` component directly under the header in both states, so the line never moves:

- running: spinner + `progressText`
- finished: status icon + `summaryText` + Details toggle, tinted by status (`warning` for `limit_reached`, `error` for error, neutral for refused)

Details expands a `RunTimeline` (MUI `Collapse`) inside the summary row's own box, so the expanded timeline shares the row's tint. It is indented to line up with the summary text. Each row shows the model it used. The full stage-to-model mapping is not repeated under the timeline. It goes to feedback only (decision 6). Each step row is a compact line. Rows with raw detail get their own small expander that reveals:
- execute rows: full args and result, pretty-printed when they parse as JSON, in a `pre` with `maxHeight` and `overflow: auto`
- plan rows: the plan steps
- synthesize rows: the draft text
- evaluate rows: the full feedback

The panel renders only while AI Summary is on (`ai=true`), and then when there is summary text or a run, so errors and refusals with no text still render. Turning AI Summary off hides any run row along with the summary.

A tool call is shown as failed when its result starts with `Error: `. Both backend paths mark failures that way (see the `chat-agent-events` delta).

*Alternatives:* MUI Lab `Timeline` is available (`@mui/lab` is a dependency) but visually heavy for a dense, compact panel, so plain `Box` rows are used. A separate drawer or dialog was rejected because the agreed layout keeps the overview inside the panel.

### 6. Feedback context

`AISummary` passes `{type: 'ai_summary', query, summary, run: compactOutcome(aiRun)}` to `FeedbackWidget`. `compactOutcome` returns `{status, path, attemptsUsed, score, models}` and is unit-tested to contain no tool results or drafts. The backend `FeedbackPayload` already allows extra fields.

### 7. Vitest for the UI's pure logic

Vitest is added as a dev dependency, with a `test` script and the existing Vite config. Tests cover `reduceRun` (keyword, insight-with-retry, refused, `RUN_ERROR` with a step left open, early close), `progressText`/`summaryText` wording, and `compactOutcome`. Component rendering is checked manually against test mode, not with DOM tests, to keep the tooling addition minimal.

*Alternatives:* no tests, relying only on manual checking, would leave the reducer, which is the riskiest logic, unverified. Jest needs more configuration on a Vite project.

### 8. Test-mode scenarios selected by query text

`mock.py` gains `_mock_insight_retry_run` (classify insight → route → plan → execute → synthesize → evaluate fail with `problem: "writing"` → synthesize attempt 2 → evaluate pass → single text message → `accepted` outcome on attempt 2) and `_mock_refused_run` (classify out of scope → refuse → refusal text → `refused` outcome). `mock_stream_fn` picks one from the request's message text: `"trend"` selects insight, `"weather"` selects refused, and anything else plays the existing keyword run. The existing keyword test is unchanged, and new tests assert the step sequences from the spec.

*Alternative:* a request flag. That was rejected because it would change the request body that the contract keeps fixed. Choosing by keyword in test mode needs no API change.

## Risks / Trade-offs

- [Contract drift: the backend changes event shapes and the reducer silently mis-renders] → The reducer ignores unknown events and fields. The test-mode scenarios are hand-written scripts of the contract; their backend tests check the scripts' own sequences, not the real pipeline, so they can drift from it.
- [Durations are client receipt times, inflated by network buffering] → Acceptable for a rough guide. They are labelled as durations only, not model latency.
- [Large tool results held in memory and the store] → One run at a time, replaced on each new search. The nested view is height-limited. Raw results are not stored beyond the current run.
- [Showing rejected drafts may confuse public users] → Behind two levels of expansion (Details, then the row's expander), and labelled with the attempt and its failed evaluation.
- [Keyword runs show text before evaluation finishes, so the evaluation could still fail] → Unchanged from today. The settled row then shows the `limit_reached` styling, and the backend appends the incomplete-answer note.

## Migration Plan

UI-only, plus test-mode additions. It deploys with the normal UI container, and rollback is reverting the UI image. Feedback logs gain a `run` field. Older entries simply lack it.
