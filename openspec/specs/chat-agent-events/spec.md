# chat-agent-events Specification

## Purpose

Defines the event stream the chat endpoints return, so any AG-UI compatible client can show the user which stages ran, which tools were called, how the answer was evaluated, and whether the system was satisfied with it.

## Requirements

### Requirement: Chat responses are AG-UI event streams
Both `/v1/chat/stream` and `/v1/chat/stream/agui` SHALL accept their existing request bodies and respond with a server-sent event stream of AG-UI events. The stream SHALL begin with `RUN_STARTED` and end with either `RUN_FINISHED` or `RUN_ERROR`.

#### Scenario: Stream framing
- **WHEN** a client posts `{"message": "river flow"}` to `/v1/chat/stream`
- **THEN** the first AG-UI lifecycle event is `RUN_STARTED` and the last event is `RUN_FINISHED`

#### Scenario: Failure
- **WHEN** a model or tool call fails in a way the pipeline cannot recover from
- **THEN** the stream ends with `RUN_ERROR` carrying a human-readable message

### Requirement: Run metadata reports the models used
Before any answer text, the stream SHALL include a `RUN_METADATA` event with a `model` field (the model that composes the answer for this query, or the classification model for a refused query) and a `models` field mapping each stage name to its configured model identifier.

#### Scenario: Metadata before text
- **WHEN** any query is processed
- **THEN** a `RUN_METADATA` event with `model` and `models` appears before the first `TEXT_MESSAGE_CONTENT` event

### Requirement: Each pipeline stage is bracketed by step events
Every stage execution SHALL be wrapped in `STEP_STARTED` and `STEP_FINISHED` events whose `stepName` is one of `classify`, `route`, `plan`, `execute`, `synthesize`, `evaluate` or `refuse`. Each `STEP_STARTED` SHALL be followed by a `CUSTOM` event named `serka.step` with value `{step, attempt, maxAttempts, model}`. `model` is null for stages that use no model, and `maxAttempts` is null before routing.

#### Scenario: Keyword run steps
- **WHEN** a `keyword` query passes evaluation on its only attempt
- **THEN** steps appear in the order classify, route, plan, execute, synthesize, evaluate, each with attempt 1

#### Scenario: Retry is visible
- **WHEN** an `insight` query's first evaluation fails with problem `data`
- **THEN** a second `plan` step follows with `serka.step` attempt 2 and maxAttempts 3

#### Scenario: Refusal steps
- **WHEN** a query is classified out of scope
- **THEN** only the `classify` and `refuse` steps appear

### Requirement: Stage results are published as custom events
The stream SHALL publish stage results as `CUSTOM` events inside their step: `serka.classification` `{inScope, label, reason}` in classify, `serka.plan` `{summary, steps}` in plan, `serka.draft` `{attempt, text}` in synthesize for `insight` queries, and `serka.evaluation` `{attempt, passed, score, problem, feedback}` in evaluate. `label` is `keyword`, `insight` or null, and `problem` is `none`, `data` or `writing`.

#### Scenario: Evaluation event
- **WHEN** an answer is evaluated
- **THEN** a `serka.evaluation` event with the attempt number, verdict, score, problem and feedback appears inside the `evaluate` step

### Requirement: Tool calls are streamed as AG-UI tool call events
Every catalogue tool call, whether chosen by a model or run directly for a `keyword` query, SHALL be streamed inside the `execute` step as `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END` and `TOOL_CALL_RESULT` events sharing one tool call id, with `toolCallName` set to the tool's name.

#### Scenario: Keyword search call
- **WHEN** a `keyword` query runs its planned search
- **THEN** the `execute` step contains one tool call event sequence named after the search tool, with its arguments and result

#### Scenario: Keyword search with a location
- **WHEN** a `keyword` query names a place, such as "river flow Wales"
- **THEN** the `execute` step contains a geocoding tool call sequence followed by the search tool call sequence

### Requirement: Exactly one answer message per run
Each run SHALL emit exactly one assistant text message (`TEXT_MESSAGE_START`, one or more `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END`), containing the final answer, the fixed refusal or, when the limit is reached, the chosen draft followed by the fixed incomplete-answer note. Drafts that are not returned SHALL NOT appear as text message content.

#### Scenario: Retried insight query
- **WHEN** an `insight` query passes evaluation on attempt 2
- **THEN** the concatenated `TEXT_MESSAGE_CONTENT` deltas equal the attempt-2 answer only

#### Scenario: Limit reached
- **WHEN** a `keyword` query fails its only evaluation
- **THEN** the concatenated `TEXT_MESSAGE_CONTENT` deltas end with the fixed incomplete-answer note

### Requirement: Every run reports its outcome
Immediately before `RUN_FINISHED`, the stream SHALL include a `CUSTOM` event named `serka.outcome` with value `{status, path, attemptsUsed, maxAttempts, score, feedback}`. `status` is `accepted`, `limit_reached` or `refused`, and `path` is `keyword`, `insight` or null. For `limit_reached`, `feedback` SHALL carry the evaluation feedback for the returned answer.

#### Scenario: Accepted outcome
- **WHEN** a query passes evaluation on attempt 1
- **THEN** `serka.outcome` has status `accepted` and attemptsUsed 1

#### Scenario: Limit reached outcome
- **WHEN** an `insight` query fails all 3 evaluations
- **THEN** `serka.outcome` has status `limit_reached`, attemptsUsed 3, maxAttempts 3, and the returned answer's score and feedback

#### Scenario: Refused outcome
- **WHEN** a query is refused
- **THEN** `serka.outcome` has status `refused`, path null and attemptsUsed 0

### Requirement: Test mode emits the same event contract
When the service runs in test mode, the mock chat stream SHALL emit events that follow this contract (lifecycle, step, custom, tool call and single text message events), so clients can be developed without Bedrock or the MCP server.

#### Scenario: Mock stream
- **WHEN** `TEST_MODE=true` and a client posts to `/v1/chat/stream`
- **THEN** the stream contains `STEP_STARTED` events, a `serka.outcome` event and `RUN_FINISHED`
