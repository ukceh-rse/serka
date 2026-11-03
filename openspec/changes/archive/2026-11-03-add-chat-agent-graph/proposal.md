# Proposal

## Why

The chat endpoint runs one Sonnet agent with every MCP tool for every query. A two-word keyword search costs as much as a multi-step research question, scope enforcement depends on a prompt instruction, nothing checks the answer before it is returned, and clients only see a flat stream of tool calls and text. An explicit, staged pipeline lets us use cheap models where they suffice, enforce scope up front, self-check answers, and show users how an answer was produced.

## What Changes

- Upgrade `pydantic-ai` from 1.61 to the latest 2.x release before any agent changes (our current usage already matches the V2 APIs).
- Replace the single chat agent with a staged pipeline: **Classify → Route → Plan → Execute → Synthesize → Evaluate**, with loops from Evaluate back to Plan (insufficient data) or Synthesize (poorly written answer).
- Classify rejects queries outside environmental science / the EIDC catalogue with a fixed refusal message (no LLM-written refusal).
- Classify labels in-scope queries as **keyword** (find datasets) or **insight** (deeper question). Keyword queries get a single attempt and run the planned search without an LLM choosing tools. Insight queries get up to 3 attempts, and an LLM chooses the tool calls.
- When Evaluate is still not satisfied after the last allowed attempt, the system returns the best-scoring draft and tells the user the answer may be incomplete.
- Every pipeline stage is streamed as standard AG-UI events (step start/finish, tool calls, text, plus documented `serka.*` custom events), so any AG-UI client can show the steps involved.
- Models are configured per stage on Amazon Bedrock, all invoked from `eu-west-2`. Cheap Amazon Nova models handle the simple stages and Claude handles the reasoning stages. **BREAKING (config)**: the single `MODELS_LLM` setting is replaced by per-stage model settings.
- The existing `/v1/chat/stream` and `/v1/chat/stream/agui` request formats are unchanged, and the current UI keeps working.

## Capabilities

### New Capabilities
- `chat-agent`: how the chat assistant handles a query: scope classification and refusal, keyword vs insight handling, attempt limits, answer self-evaluation, incomplete-answer signalling, and model/region constraints.
- `chat-agent-events`: the streamed event contract that exposes each pipeline stage, tool call, evaluation, and final outcome to clients.

### Modified Capabilities
<!-- None: no existing specs in openspec/specs/. -->

## Impact

- **Code**: `src/serka/routers/dependencies.py` (`get_stream_fn` builds the pipeline instead of a single agent), new pipeline module(s) under `src/serka/`, `src/serka/prompts.py` (per-stage prompts replace `AGENT_PROMPT`), `src/serka/settings.py` (per-stage models), `src/serka/routers/mock.py` (mock stream emits the new events).
- **Dependencies**: `pydantic-ai[bedrock]` → 2.x in `pyproject.toml` / `uv.lock`.
- **Config**: `.env.example` and deployment env replace `MODELS_LLM` with per-stage model IDs. Claude models in `eu-west-2` require EU cross-region inference profile IDs and model access enabled in the AWS account. The Terraform IAM policy already allows `bedrock:InvokeModel*` on `*`.
- **API**: same endpoints and request bodies; the response stream gains `STEP_STARTED`/`STEP_FINISHED` and `CUSTOM` events. Existing UI event handling is unaffected.
- **Tests**: `tests/test_app.py`, new pipeline unit tests, `scripts/smoke-test.py` chat checks.
- **Out of scope**: OpenRouter, model escalation between attempts, graph state persistence/replay, an offline evaluation benchmark, UI changes to render the new step events.
