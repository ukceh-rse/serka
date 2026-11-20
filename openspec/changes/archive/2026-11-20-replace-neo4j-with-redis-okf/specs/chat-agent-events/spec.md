# Spec Delta

## MODIFIED Requirements

### Requirement: Run metadata reports the models used
Before any answer text, the stream SHALL include a `RUN_METADATA` event with a `model` field (the model that composes the answer for this query, the classification model for a refused query, or the model that composed a cached answer) and a `models` field mapping each stage name to its configured model identifier.

#### Scenario: Metadata before text
- **WHEN** any query is processed
- **THEN** a `RUN_METADATA` event with `model` and `models` appears before the first `TEXT_MESSAGE_CONTENT` event

#### Scenario: Cached answer model
- **WHEN** a query is answered from the cache
- **THEN** `RUN_METADATA.model` is the model recorded with the cached answer

### Requirement: Each pipeline stage is bracketed by step events
Every stage execution SHALL be wrapped in `STEP_STARTED` and `STEP_FINISHED` events whose `stepName` is one of `cache`, `classify`, `route`, `plan`, `execute`, `synthesize`, `evaluate`, `refuse` or `limit`. Each `STEP_STARTED` SHALL be followed by a `CUSTOM` event named `serka.step` with value `{step, attempt, maxAttempts, model}`. `model` is null for stages that use no model, and `maxAttempts` is null before routing.

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

#### Scenario: Cached answer steps
- **WHEN** a query is answered from the cache
- **THEN** only the `cache` step appears

#### Scenario: Cache miss
- **WHEN** a first-turn query is looked up in the cache and misses
- **THEN** a `cache` step appears before `classify`, and the run continues with the usual steps

### Requirement: Every run reports its outcome
Immediately before `RUN_FINISHED`, the stream SHALL include a `CUSTOM` event named `serka.outcome` with value `{status, path, attemptsUsed, maxAttempts, score, feedback}`. `status` is `accepted`, `limit_reached`, `refused`, `insight_limit_reached` or `cached`, and `path` is `keyword`, `insight` or null. For `limit_reached`, `feedback` SHALL carry the evaluation feedback for the returned answer.

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

#### Scenario: Cached outcome
- **WHEN** a query is answered from the cache
- **THEN** `serka.outcome` has status `cached`, the path and score recorded with the cached answer, attemptsUsed 0, and null maxAttempts and feedback
