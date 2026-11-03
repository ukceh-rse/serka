# Tasks

## 1. Upgrade pydantic-ai to 2.x

- [x] 1.1 Bump `pydantic-ai[bedrock]` in `pyproject.toml` to the latest 2.x and run `uv lock && uv sync`; verify `uv run python -c "import pydantic_ai, pydantic_graph; print(pydantic_ai.__version__)"` prints a 2.x version
- [x] 1.2 Fix any import or API breakage in `src/serka/routers/dependencies.py` against the V2 migration guide; verify `uv run pytest` passes and `uv run mypy` reports no new errors
- [x] 1.3 Run `uv run scripts/smoke-test.py` against the existing single agent; verify the "chat answers pike question" check passes before any pipeline work starts

## 2. Per-stage model configuration

- [x] 2.1 Look up the EU inference profile IDs for Claude Haiku 5.5 and Sonnet 5.5 and the Nova Micro/Lite model IDs with `aws bedrock list-inference-profiles --region eu-west-2` / `list-foundation-models`; verify each ID responds to a one-line Converse call from `eu-west-2` (extend `scripts/test_bedrock.py`)
- [x] 2.2 In `src/serka/settings.py` replace `models_llm` with `aws_region` (default `eu-west-2`) and the seven `models_*` stage fields, using the defaults from design.md decision 4; verify a unit test shows that env vars override each field individually
- [x] 2.3 Add a `StageModels` builder that creates one `BedrockConverseModel` per stage with an explicit `BedrockProvider(region_name=settings.aws_region)`; verify a unit test asserts every stage model's provider region is `eu-west-2` and that tests can substitute `TestModel` per stage
- [x] 2.4 Update `.env.example` (remove `MODELS_LLM`, add the `MODELS_*` stage vars with comments on which stage each controls); verify `Settings()` loads cleanly from the example file

## 3. Event emitter

- [x] 3.1 Spike (time-box 1h): check whether pydantic-ai 2.x exposes a public AG-UI event-stream converter usable for one inner agent run; record the outcome as a short note in design.md decision 6 and verify the note states which approach 3.3 uses
- [x] 3.2 Implement the queue-backed `Emitter` with helpers for run lifecycle, step start/finish (+ `serka.step`), custom events, tool call sequences, text messages and the raw `RUN_METADATA` line; verify unit tests decode its SSE output and assert event types, ordering and payload field names match `specs/chat-agent-events`
- [x] 3.3 Implement mapping of inner-agent tool call and text delta events onto the emitter (or adopt the converter found in 3.1); verify a test using `FunctionModel` that calls a fake tool produces one `TOOL_CALL_START/ARGS/END/RESULT` sequence with a shared id
- [x] 3.4 Implement the stream driver that runs the graph in a task, drains the queue into a `StreamingResponse`, and ends with `RUN_FINISHED`, or `RUN_ERROR` on exception; verify tests cover both endings, including a stage that raises

## 4. Pipeline state, prompts and nodes

- [x] 4.1 Split `AGENT_PROMPT` in `src/serka/prompts.py` into classify, plan (keyword/insight), execute, synthesize and evaluate prompts plus the fixed refusal and incomplete-answer constants, then remove `AGENT_PROMPT`; verify `grep -r AGENT_PROMPT src tests` returns nothing and the synthesize prompt keeps the citation/format rules
- [x] 4.2 Define pipeline state, deps and structured output models (`Classification`, `SearchParams`, `Plan`, `Evaluation`); verify mypy strict passes on the new module
- [x] 4.3 Implement `Classify` (scope + label in one call, using history), `Route` (label → max attempts 1/3, emits `RUN_METADATA`) and `Refuse` (fixed text, `refused` outcome); verify unit tests for in-scope, out-of-scope, follow-up-with-history and refusal event scenarios in `specs/chat-agent`
- [x] 4.4 Implement `Plan` for both paths, with previous plan and feedback on a `data` retry, emitting `serka.plan`; verify unit tests with `TestModel` assert keyword yields `SearchParams` and insight yields `{summary, steps}`
- [x] 4.5 Implement `Execute`: keyword runs geocode (when a location is set) then search directly; insight runs the Haiku agent with the MCP toolset and collects compacted tool results; verify tests with a fake tool caller assert the keyword path makes no model-chosen calls and that the geocode-then-search event order matches the spec
- [x] 4.6 Implement `Synthesize`: keyword streams the answer live with the message left open; insight emits `serka.draft` only; writing retries reuse the existing tool results; verify tests assert no `TEXT_MESSAGE_CONTENT` is emitted for insight drafts
- [x] 4.7 Implement `Evaluate`: emit `serka.evaluation`, record the draft score, then loop to Plan (`data`) or Synthesize (`writing`) while attempts remain; otherwise end with the best draft, the note on `limit_reached`, the single answer message and `serka.outcome`; verify scripted-model tests cover accepted on attempt 1, keyword limit reached, insight data retry, insight writing retry, and the 3-attempt best-draft selection (scores 3, 2, 2 → attempt 1)
- [x] 4.8 Assemble the `Graph` from the nodes and add its `Graph.render()` diagram to the docs; verify an end-to-end test with scripted models asserts the full keyword and refusal step sequences from `specs/chat-agent-events`

## 5. Wiring, test mode and API docs

- [x] 5.1 Rewrite `get_stream_fn` in `src/serka/routers/dependencies.py` to build per-run deps and run the pipeline, mapping `RunAgentInput` to the latest user message plus history; remove the now-unused single-agent code; verify `tests/test_app.py` passes and a new test posts to both `/v1/chat/stream` and `/v1/chat/stream/agui` with the pipeline using scripted models
- [x] 5.2 Rewrite `mock_stream_fn` in `src/serka/routers/mock.py` to replay a scripted keyword run that follows the new contract; verify a test with `TEST_MODE=true` sees `STEP_STARTED`, `serka.outcome` and `RUN_FINISHED`, and that the UI dev server still renders the mock answer
- [x] 5.3 Document the chat pipeline and event contract (stages, `serka.*` payloads, outcome statuses, per-stage model env vars) in `README.md`; verify every `serka.*` event and `MODELS_*` variable in the code appears in the docs

## 6. Integration checks

- [x] 6.1 Extend `scripts/smoke-test.py` to collect all events from the chat call and check: steps include classify→evaluate, a `serka.outcome` is present, an off-topic question returns exactly the refusal text with status `refused`, and the existing pike-question answer check still passes; verify by running `uv run scripts/smoke-test.py` with real Bedrock in `eu-west-2`
- [x] 6.2 Run one keyword and one insight query manually against the smoke environment and capture the event streams in the PR description; verify the insight stream shows MCP tool calls chosen by the model and the models in `RUN_METADATA.models` match the configured stage models
