# Spec Delta

## MODIFIED Requirements

### Requirement: Live progress line while the summary generates
While a summary run is in progress, the AI Summary panel SHALL show a single progress line under its header. The line describes the stage currently running in plain words. When the run allows more than one attempt, it includes the attempt number and attempt limit for the answer stages (`synthesize`, `evaluate`) and for any stage on a retry. During `execute` it names the tool being called.

#### Scenario: Stage shown as it starts
- **WHEN** a `STEP_STARTED` event for `evaluate` arrives with `serka.step` `{attempt: 2, maxAttempts: 2}`
- **THEN** the progress line reads as checking the answer, attempt 2 of 2

#### Scenario: Tool call named
- **WHEN** a `TOOL_CALL_START` event with `toolCallName` `search` arrives inside the `execute` step
- **THEN** the progress line says the catalogue is being searched and names `search`

#### Scenario: Keyword answer streams under the line
- **WHEN** a `keyword` run streams answer text during `synthesize` and then starts `evaluate`
- **THEN** the streamed text stays visible and the progress line shows the evaluate stage above it

### Requirement: Progress line settles into a run summary row
When the run ends, the progress line SHALL be replaced, in the same position, by a summary row. The row shows the path, the number of catalogue tool calls, the outcome with the attempts used, the score and the date. The "Model" and "Date" provenance chips SHALL NOT be shown.

#### Scenario: Accepted insight run
- **WHEN** a run ends with `serka.outcome` `{status: "accepted", path: "insight", attemptsUsed: 2, maxAttempts: 2, score: 4}` after four tool calls
- **THEN** the row shows an insight query, 4 catalogue calls, accepted on attempt 2, score 4 of 5, and today's date

#### Scenario: No chips
- **WHEN** any run has finished
- **THEN** no "Model:" or "Date:" chip is rendered in the AI Summary panel

### Requirement: Summary row distinguishes the run outcome
The summary row SHALL look different for each outcome: `accepted`, `limit_reached`, `refused`, a daily usage limit, and a run that ended in error. A `limit_reached` row SHALL say that the best of the attempts was returned without fully passing. A `refused` row SHALL show the classification reason. A daily usage limit row SHALL state the limit without presenting it as an error or as out of scope.

#### Scenario: Limit reached
- **WHEN** `serka.outcome` has status `limit_reached` with attemptsUsed 2
- **THEN** the row is shown with warning styling and says the best of 2 attempts was returned without fully passing

#### Scenario: Stopped at the retrieval limit
- **WHEN** `serka.outcome` has status `limit_reached` with attemptsUsed below maxAttempts
- **THEN** the row says retrieval stopped at its limit and the best answer was returned without fully passing, not that the attempts ran out

#### Scenario: Refused
- **WHEN** a run ends with status `refused` after `serka.classification` `{inScope: false, reason: "Not about environmental data"}`
- **THEN** the row says the query was out of scope and shows "Not about environmental data"

#### Scenario: Insight limit
- **WHEN** `serka.outcome` has status `insight_limit_reached`
- **THEN** the row says detailed analysis has reached its daily limit, with no error or out-of-scope wording

### Requirement: Summary feedback carries the run outcome
Feedback submitted from the AI Summary SHALL include, along with the query and summary, the run's status, path, attempts used, score and the per-stage model mapping. It SHALL NOT include tool results or draft text. A daily usage limit message SHALL NOT offer feedback, because it is not an answer.

#### Scenario: Thumbs down on a limit-reached summary
- **WHEN** the user gives negative feedback on a summary whose run ended `limit_reached` on attempt 2 with score 2
- **THEN** the submitted payload contains status `limit_reached`, the path, attemptsUsed 2, score 2 and the stage-to-model mapping

#### Scenario: No bulky fields
- **WHEN** any AI Summary feedback is submitted
- **THEN** the payload contains no tool call results and no draft text

### Requirement: Test mode can exercise every summary state
In test mode, the summary stream SHALL also offer scripted runs that follow the chat event contract: an `insight` run that fails one evaluation and is then accepted, a `refused` run, and an `insight_limit_reached` run. Which scripted run plays SHALL be chosen by the query text, with the existing keyword run as the default.

#### Scenario: Insight retry run
- **WHEN** the service is in test mode and the query selects the insight scenario
- **THEN** the stream contains two synthesize and two evaluate steps, the first evaluation failing, and an `accepted` outcome on attempt 2

#### Scenario: Refused run
- **WHEN** the service is in test mode and the query selects the refusal scenario
- **THEN** the stream contains only the classify and refuse steps and a `refused` outcome

#### Scenario: Insight limit run
- **WHEN** the service is in test mode and the query selects the insight limit scenario
- **THEN** the stream contains only the classify, route and limit steps, the fixed insight limit message and an `insight_limit_reached` outcome

## ADDED Requirements

### Requirement: The type filter does not affect the summary
Changing the result type filter SHALL re-run only the search. It SHALL NOT start, stop or reset the AI Summary, and SHALL NOT use any daily allowance.

#### Scenario: Filter changed after a summary
- **WHEN** a summary is shown and the user changes the type filter
- **THEN** the results update, the summary and its run details stay as they were, and no request is sent to `/v1/chat/stream`

#### Scenario: Filter changed while a summary generates
- **WHEN** a summary is generating and the user changes the type filter
- **THEN** the summary run continues

### Requirement: Rejected summary requests show the limit message
When a summary request is rejected by a daily cap, the AI Summary SHALL stop loading and show the server's limit message in the summary row as a daily usage limit, not as an error.

#### Scenario: Daily cap reached
- **WHEN** the summary request returns HTTP 429 with a message
- **THEN** the loading indicator stops and the row shows that message with daily limit styling
- **AND** the words "Something went wrong" do not appear

#### Scenario: Other request failures
- **WHEN** the summary request returns an HTTP error other than 429
- **THEN** the row shows the existing error state
