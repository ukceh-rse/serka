# Spec Delta

## MODIFIED Requirements

### Requirement: Chat responses are AG-UI event streams
`/v1/chat/stream`, and `/v1/chat/stream/agui` when chat is enabled, SHALL accept their existing request bodies and respond with a server-sent event stream of AG-UI events, unless the request is rejected before a run starts. The stream SHALL begin with `RUN_STARTED` and end with either `RUN_FINISHED` or `RUN_ERROR`. A rejected request SHALL receive a plain HTTP error response with no event stream.

#### Scenario: Stream framing
- **WHEN** a client posts `{"message": "river flow"}` to `/v1/chat/stream`
- **THEN** the first AG-UI lifecycle event is `RUN_STARTED` and the last event is `RUN_FINISHED`

#### Scenario: Failure
- **WHEN** a model or tool call fails in a way the pipeline cannot recover from
- **THEN** the stream ends with `RUN_ERROR` carrying a human-readable message

#### Scenario: Rejected before the stream
- **WHEN** a request is rejected by a daily cap or the query length limit
- **THEN** the response is an HTTP error with no `RUN_STARTED` event

### Requirement: Each pipeline stage is bracketed by step events
Every stage execution SHALL be wrapped in `STEP_STARTED` and `STEP_FINISHED` events whose `stepName` is one of `classify`, `route`, `plan`, `execute`, `synthesize`, `evaluate`, `refuse` or `limit`. Each `STEP_STARTED` SHALL be followed by a `CUSTOM` event named `serka.step` with value `{step, attempt, maxAttempts, model}`. `model` is null for stages that use no model, and `maxAttempts` is null before routing.

#### Scenario: Keyword run steps
- **WHEN** a `keyword` query passes evaluation on its only attempt
- **THEN** steps appear in the order classify, route, plan, execute, synthesize, evaluate, each with attempt 1

#### Scenario: Retry is visible
- **WHEN** an `insight` query's first evaluation fails with problem `data`
- **THEN** a second `plan` step follows with `serka.step` attempt 2 and maxAttempts 2

#### Scenario: Refusal steps
- **WHEN** a query is classified out of scope
- **THEN** only the `classify` and `refuse` steps appear

#### Scenario: Insight limit steps
- **WHEN** a query is stopped by the daily insight cap
- **THEN** only the `classify`, `route` and `limit` steps appear

### Requirement: Every run reports its outcome
Immediately before `RUN_FINISHED`, the stream SHALL include a `CUSTOM` event named `serka.outcome` with value `{status, path, attemptsUsed, maxAttempts, score, feedback}`. `status` is `accepted`, `limit_reached`, `refused` or `insight_limit_reached`, and `path` is `keyword`, `insight` or null. For `limit_reached`, `feedback` SHALL carry the evaluation feedback for the returned answer.

#### Scenario: Accepted outcome
- **WHEN** a query passes evaluation on attempt 1
- **THEN** `serka.outcome` has status `accepted` and attemptsUsed 1

#### Scenario: Limit reached outcome
- **WHEN** an `insight` query fails both evaluations
- **THEN** `serka.outcome` has status `limit_reached`, attemptsUsed 2, maxAttempts 2, and the returned answer's score and feedback

#### Scenario: Refused outcome
- **WHEN** a query is refused
- **THEN** `serka.outcome` has status `refused`, path null and attemptsUsed 0

#### Scenario: Insight limit outcome
- **WHEN** a query is stopped by the daily insight cap
- **THEN** `serka.outcome` has status `insight_limit_reached`, path `insight`, attemptsUsed 0, maxAttempts 2, and null score and feedback
- **AND** the stream ends with `RUN_FINISHED`, not `RUN_ERROR`
