# Proposal

## Why

The chat pipeline now streams a detailed account of every run: stages, attempts, tool calls, evaluations and an outcome (`chat-agent-events`). The Results page's AI Summary ignores almost all of it. It still waits for `THINKING_*` events that are no longer emitted, so for an insight query the user sees only a spinner until the whole answer arrives at once. It hangs if the run ends in `RUN_ERROR`. Its only provenance is two chips, "Model" and "Date", and the single model is now ambiguous because every stage has its own model. The event stream already contains everything needed to show users what is happening and how the answer was produced.

## What Changes

- While the summary is generating, the AI Summary panel shows a **live progress line** under its header. The line says in plain words which stage is running, which tool is being called and which attempt this is, and it briefly notes when an attempt failed evaluation and is being retried.
- When the run ends, the progress line **settles in place into a summary row**: path, number of catalogue calls, outcome and attempt, score and date. It has a distinct look for `accepted`, `limit_reached`, `refused` and error runs.
- The summary row expands into a **run timeline**. Each row shows one stage execution: its result (classification, plan, tool calls with short arguments, evaluation score and problem), its model and its duration, followed by the outcome. Each row has a nested expander for raw detail: full tool arguments and results, plan steps, rejected draft text and evaluator feedback.
- **Removed**: the "Model" and "Date" provenance chips, and the `THINKING_*` handling and the store fields that only existed for them.
- **Fixed**: a run that ends in `RUN_ERROR`, or whose stream closes without `RUN_FINISHED`, stops the loading state and shows an error.
- AI Summary **feedback includes a compact run outcome**: status, path, attempts used, score and per-stage models.
- **Test mode** gains scripted insight-with-retry and refused runs alongside the existing keyword run, so every summary state can be seen without Bedrock or the MCP server.

Out of scope: the Chat page beyond ending its loading state on `RUN_ERROR`, and any change to the chat event contract other than marking failed tool results.

## Capabilities

### New Capabilities
- `ai-summary-run-overview`: How the Results page AI Summary presents a chat run to the user: live progress, the settled summary row, the expandable run timeline with raw detail, error handling, and the run outcome attached to summary feedback.

### Modified Capabilities
- `chat-agent-events`: a failed tool call's `TOOL_CALL_RESULT` content starts with `Error: ` on the model-chosen (insight) path too, not only for directly run keyword calls, so the timeline can show the failure. The additional test-mode runs still follow its existing "Test mode emits the same event contract" requirement.

## Impact

- **UI**: `ui/src/api/chat.ts` (event types, stream termination), `ui/src/stores/searchStore.ts` (run trace replaces `aiModel`/`aiThinking`), `ui/src/pages/ResultsPage.tsx` (feeds events into the trace), `ui/src/components/AISummary.tsx` (progress line, summary row, timeline; chips removed), plus new run-trace reducer and timeline component modules.
- **UI tooling**: adds a test runner (Vitest) as a dev dependency to unit-test the run-trace reducer.
- **Backend (test mode only)**: `src/serka/routers/mock.py` gains extra scripted runs selected by the query text; `tests/test_chat_api.py` covers them.
- **Feedback**: additional fields in the AI Summary feedback payload. `FeedbackPayload` already accepts extra fields, so the endpoint does not change.
- **Backend**: `src/serka/chat/events.py` prefixes `Error: ` on failed model-chosen tool results; `tests/test_chat_events.py` covers it.
- **No API changes.** The only event contract change is the failed tool result marking above.
