# Design

## Context

- The chat stream is built in `get_stream_fn` (`src/serka/routers/dependencies.py`). It creates one `Agent(BedrockConverseModel(settings.models_llm), instructions=AGENT_PROMPT, toolsets=[MCPServerStreamableHTTP(...)])` and hands it to `AGUIAdapter`, adding a non-standard `RUN_METADATA` SSE event in front. The router (`src/serka/routers/chat.py`) and the test-mode override (`mock_stream_fn` in `src/serka/routers/mock.py`) depend only on the `StreamFn` signature `(run_input, request) -> Response`, so the pipeline can be swapped in behind it.
- `AGUIAdapter` drives a single `Agent`. It cannot drive a multi-stage graph, so the pipeline needs its own event emitter.
- The UI (`ui/src/api/chat.ts`) reads `data:` lines and acts on `TEXT_MESSAGE_CONTENT`, `TOOL_CALL_START`/`END`, `RUN_METADATA` and `RUN_FINISHED`, ignoring other types. It concatenates text deltas, which is why the spec allows only one text message per run.
- The MCP server exposes `search`, `geocode_location`, `get_entity`, `get_relations`, `get_contributors`, `find_by_contributor`, `list_datasets`, `get_content` and `describe_ontology`. `get_mcp_search` already shows the keyword flow: geocode a location into a bounding box, then call `search`.
- pydantic-ai is pinned at 1.61. In 2.x, `GraphBuilder` is top-level, `pydantic_graph.persistence` and `pydantic_graph.mermaid` are removed (use `Graph.render()`), and the `BaseNode` API remains supported. Our current imports are all valid in V2.
- `eu-west-2` offers Nova Micro, Lite and Pro in-region. Claude Haiku 5.5 and Sonnet 5.5 are only available there through geo or global cross-region inference profiles.

## Goals / Non-Goals

**Goals:**
- A pipeline whose stages, retries and outcome are fully visible in the event stream (see `specs/chat-agent-events`).
- Every stage unit-testable without Bedrock or the MCP server.
- Per-stage model choice changeable through env vars alone.

**Non-Goals:**
- Parallel retrieval branches (no need for `GraphBuilder` map/broadcast).
- Persisting or replaying runs, or a `/runs/{id}` endpoint.
- Rendering steps in the UI. The UI must merely keep working.
- Tuning prompts or models beyond a working baseline. That waits for a later evaluation exercise.

## Decisions

### 1. Upgrade pydantic-ai first, as a separate step
Bump `pydantic-ai[bedrock]` to the latest 2.x and re-lock before any pipeline work, then run unit tests and the smoke test against the *existing* agent. This isolates upgrade regressions from pipeline regressions. *Alternative:* upgrade together with the pipeline. Rejected because failures would be ambiguous.

### 2. `BaseNode` state machine, one node per stage
Nodes `Classify`, `Route`, `Plan`, `Execute`, `Synthesize`, `Evaluate` and `Refuse` are dataclass `BaseNode`s whose `run()` return annotations define the edges:

```
Classify   -> Refuse | Route
Route      -> Plan
Plan       -> Execute
Execute    -> Synthesize
Synthesize -> Evaluate
Evaluate   -> Plan | Synthesize | End[Answer]
Refuse     -> End[Answer]
```

`Plan`, `Execute` and `Synthesize` branch internally on `state.label` (keyword/insight) rather than being split into per-path nodes. Node names then map 1:1 onto the spec's `stepName` values. *Alternative:* `GraphBuilder` with decorated steps. Its advantages (parallelism, reducers) don't apply to a sequential loop, and `BaseNode` keeps each stage's edges in its type signature. `Graph.render()` gives the diagram for docs.

### 3. Shared state and dependencies
- **State** (mutable, one per run): `query`, `history`, `classification`, `label`, `max_attempts`, `attempt`, `plan`, `tool_results` (list of `{tool, args, result}`), `feedback` (last evaluation feedback), `drafts` (list of `{attempt, text, evaluation}`).
- **Deps** (per run): a `StageModels` mapping stage → model, a tool caller (the MCP toolset), and an `Emitter` (decision 6).
- Attempt counting: `attempt` starts at 1 in `Route` and increments only when `Evaluate` loops back. Each loop-back therefore starts a new attempt, whether it goes to `Plan` (data) or `Synthesize` (writing). On a `data` retry, `tool_results` are replaced, not accumulated.
- Best draft: `max(drafts, key=score)`. Ties go to the earliest attempt.

### 4. Stage behaviour

| Stage | Model setting (default) | Output | Notes |
|---|---|---|---|
| Classify | `models_classify` (Nova Lite) | `{in_scope, label, reason}` | One structured-output call for both scope and label. Recent history is included so follow-ups classify correctly. |
| Route | none | sets `label`, `max_attempts` (1 or 3) | Plain code. Emits `RUN_METADATA`. |
| Refuse | none | fixed refusal text | Text constant lives in `prompts.py` (reuses today's wording). |
| Plan (keyword) | `models_plan_keyword` (Nova Micro) | `SearchParams {query, return_type, location, published_after, published_before}` | Mirrors the parameters `get_mcp_search` already supports. |
| Plan (insight) | `models_plan_insight` (Sonnet 5.5) | `{summary, steps[]}` | Receives previous plan and feedback on a `data` retry. |
| Execute (keyword) | none | tool results | `geocode_location` when `location` is set, then `search`, called directly via the MCP client. |
| Execute (insight) | `models_execute_insight` (Haiku 5.5) | tool results | An agent with the MCP toolset, instructed with the plan. Tool results are collected from its run. Its own text output is discarded. |
| Synthesize | `models_synthesize_keyword` (Nova Lite) / `models_synthesize_insight` (Sonnet 5.5) | answer text | The prompt carries today's grounding, citation and format rules from `AGENT_PROMPT`. |
| Evaluate | `models_evaluate` (Haiku 5.5) | `{passed, score 1-5, problem, feedback}` | Sees query, tool results and draft. Uses a different model than Synthesize to reduce self-grading bias. |

`AGENT_PROMPT` is split into per-stage prompts and removed.

### 5. Model configuration and region
`Settings` gains `aws_region: str = "eu-west-2"` and the seven `models_*` stage fields, replacing `models_llm`. Each model is built as `BedrockConverseModel(id, provider=BedrockProvider(region_name=settings.aws_region))`, so the region is explicit rather than inherited from `AWS_DEFAULT_REGION`. Claude stages default to EU geo inference profile IDs. Swapping to global profiles is an env change only. Exact IDs are confirmed with `aws bedrock list-inference-profiles --region eu-west-2` during implementation. *Alternative:* one `models_fast` / `models_strong` pair. Rejected because the table above already uses three different models, and per-stage settings cost nothing extra.

### 6. Event emission: queue-backed emitter, hand-mapped agent events
```
endpoint -> start task: graph.run(Classify(), state, deps)
              |  nodes call emitter.step(...), emitter.custom(...), emitter.tool_call(...), emitter.text(...)
              v
        asyncio.Queue  --> async generator --> SSE encode --> StreamingResponse
              (sentinel / exception ends the stream: RUN_FINISHED or RUN_ERROR)
```
- The `Emitter` wraps the queue with typed helpers that build `ag_ui.core` events (`StepStartedEvent`, `CustomEvent`, `ToolCall*Event`, `TextMessage*Event`, `RunStarted/Finished/ErrorEvent`) and encode them with the `ag_ui` encoder. `RUN_METADATA` is not an AG-UI type, so it is written as a raw SSE line, the same as today.
- Model-backed stages run their agent with an event stream handler. `FunctionToolCallEvent` and `FunctionToolResultEvent` map to `TOOL_CALL_START/ARGS/END/RESULT`. Text deltas map to `TEXT_MESSAGE_CONTENT` only where text is streamed live (below). Directly executed keyword tool calls emit the same tool call events.
- **Text policy** (spec: exactly one answer message). The keyword path has a single attempt, so Synthesize streams its tokens live as the answer message. `TEXT_MESSAGE_END` is held until after Evaluate so the incomplete-answer note can be appended as a final delta. Insight drafts are not streamed. Each is emitted as `serka.draft`, and the chosen answer is sent as one text message after the final evaluation. This trades live typing on insight answers for never showing text that gets replaced.
- *Alternative:* reuse pydantic-ai's internal AG-UI event-stream class per inner agent. A short spike (task 3.1) checks whether it is public and composable in 2.x. If not, we use the hand mapping, which covers only the handful of event types listed above.
- **Spike outcome (task 3.1, pydantic-ai 2.65):** `pydantic_ai.ui.ag_ui.AGUIEventStream` is public, but it is a whole-run transformer: it owns run lifecycle and per-response message identities, and opens a `TEXT_MESSAGE_START` for every model response (including content-free ones before tool calls). Using it for an inner run would mean filtering its text/lifecycle output and fighting its turn state. **Task 3.3 uses the hand mapping**: `FunctionToolCallEvent` → `TOOL_CALL_START/ARGS/END`, `FunctionToolResultEvent` → `TOOL_CALL_RESULT`, and text deltas only where streamed live.

### 7. Wiring and test mode
`get_stream_fn` builds the graph and per-run deps, returning a `StreamFn` that converts `RunAgentInput` to `(query = last user message, history = earlier messages)`. The router and endpoints are unchanged. `mock_stream_fn` is rewritten to replay a scripted keyword run that follows the new contract.

### 8. Testing approach
Nodes are tested with pydantic-ai `TestModel`/`FunctionModel` injected through `StageModels`, and with a fake tool caller instead of MCP. Event-contract tests run the whole graph with scripted models and assert on the decoded event sequence. The smoke test asserts the real stream contains the step and outcome events.

## Risks / Trade-offs

- [Insight tool results (JSON-LD) are large and inflate tokens for Synthesize and Evaluate] → Pass compacted results (`@graph` hits, key fields only) to downstream stages, and cap the size per result.
- [Nova Micro misclassifies borderline queries, either refusing valid ones or labelling insight as keyword] → `serka.classification` makes this observable. Prompt with explicit examples. Swap the model by env var if the deeper evaluation shows a problem. *Update (2026-11-03):* the manual run refused valid provenance and contributor questions on Nova Micro (about 8 in 70). Two changes fixed it: putting `reason` before `category` in `Classification`, and switching the default to Nova Lite. The result was 0 scope errors in 140 classifications. Classify also gets 2 output retries, because Nova occasionally returns structured output that fails validation.
- [Evaluator is too lenient or too harsh, wasting retries or flagging good answers] → Scores and outcomes are in the stream for later analysis. Attempt caps bound the cost.
- [Insight answers no longer type out live] → Accepted for correctness. Progress is still visible through step, tool call and `serka.draft` events.
- [Up to 3 Sonnet plan and synthesis passes make worst-case insight latency high] → Capped at 3 attempts. `writing` retries skip retrieval.
- [Claude models need geo inference profiles and account model access in `eu-west-2`] → Verify IDs and access before deploy (task 2.x). Nova stages work regardless.
- [Price figures used for model choice came from third-party sources] → Confirm against the AWS pricing page before relying on cost estimates.

## Migration Plan

1. Merge the upgrade (task group 1) on its own and verify it.
2. Before deploying the pipeline, enable Bedrock model access for the chosen Claude models and set the new `MODELS_*` env vars (see `.env.example`). Unset `MODELS_LLM`.
3. Deploy and run `scripts/smoke-test.py` against the environment.
4. Rollback: redeploy the previous image with `MODELS_LLM` restored. There is no data migration.

## Open Questions

- Exact EU inference profile IDs for Haiku 5.5 and Sonnet 5.5 in `eu-west-2`. These only fill in config defaults.
