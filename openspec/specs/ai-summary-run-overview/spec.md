# ai-summary-run-overview Specification

## Purpose

Shows Results page users what the chat pipeline is doing while an AI Summary is generated and, afterwards, how that summary was produced: stages, tool calls, evaluations, models and outcome.

## Requirements

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

### Requirement: Failed attempts are announced before a retry
When an evaluation fails and the run continues with another attempt, the progress line SHALL briefly state that the attempt did not pass and give the evaluator's feedback before describing the next stage.

#### Scenario: Retry after a data problem
- **WHEN** `serka.evaluation` `{attempt: 1, passed: false, problem: "data", feedback: "Missing date ranges"}` arrives and a further step starts
- **THEN** the user sees that attempt 1 did not pass, with "Missing date ranges", before the line moves on to the next stage

### Requirement: Progress line settles into a run summary row
When the run ends, the progress line SHALL be replaced, in the same position, by a summary row. The row shows the path, the number of catalogue tool calls, the outcome with the attempts used, the score and the date. The "Model" and "Date" provenance chips SHALL NOT be shown.

#### Scenario: Accepted insight run
- **WHEN** a run ends with `serka.outcome` `{status: "accepted", path: "insight", attemptsUsed: 2, maxAttempts: 2, score: 4}` after four tool calls
- **THEN** the row shows an insight query, 4 catalogue calls, accepted on attempt 2, score 4 of 5, and today's date

#### Scenario: No chips
- **WHEN** any run has finished
- **THEN** no "Model:" or "Date:" chip is rendered in the AI Summary panel

### Requirement: Summary row distinguishes the run outcome
The summary row SHALL look different for each outcome: `accepted`, `limit_reached`, `refused`, `cached`, a daily usage limit, and a run that ended in error. A `limit_reached` row SHALL say that the best of the attempts was returned without fully passing. A `refused` row SHALL show the classification reason. A daily usage limit row SHALL state the limit without presenting it as an error or as out of scope. A `cached` row SHALL say that a saved answer to a similar question was returned.

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

#### Scenario: Cached
- **WHEN** `serka.outcome` has status `cached` with path `keyword` and score 4
- **THEN** the row says a saved answer to a similar question was returned, with the keyword path and score 4 of 5, and no attempt count or tool call count

### Requirement: Run errors end the loading state
If the stream ends with `RUN_ERROR`, or closes or fails without `RUN_FINISHED`, the AI Summary SHALL stop showing as loading. Its summary row SHALL show that something went wrong, using the error message when one is given.

#### Scenario: RUN_ERROR
- **WHEN** the stream ends with `RUN_ERROR` carrying a message
- **THEN** the loading indicator stops and the summary row shows an error state with that message

#### Scenario: Stream closes early
- **WHEN** the stream closes after some step events but with no `RUN_FINISHED` or `RUN_ERROR`
- **THEN** the loading indicator stops and the summary row shows an error state

### Requirement: Summary row expands into a run timeline
The summary row SHALL expand on demand into a timeline with one row for each stage execution, in order, followed by an outcome row. Each stage row shows the stage and attempt, its result, its model when it has one, and its duration.

#### Scenario: Stage results shown
- **WHEN** the user expands the timeline of a finished insight run
- **THEN** the classify row shows the label and reason, the plan row shows the plan summary, the execute row lists each tool call by name with short arguments and success or failure, and each evaluate row shows its score, problem and whether it passed

#### Scenario: Retries appear as repeated rows
- **WHEN** a run used two attempts
- **THEN** the timeline shows the repeated stages once for each attempt, labelled with their attempt numbers

#### Scenario: Collapsed by default
- **WHEN** a run finishes
- **THEN** the timeline is collapsed until the user asks to see details

### Requirement: Timeline rows reveal raw detail on demand
Each timeline row that has raw detail SHALL offer its own expander. Execute rows show full tool arguments and results, plan rows show the plan steps, synthesize rows show the draft text, and evaluate rows show the full evaluator feedback. Long tool results SHALL be shown in a bounded, scrollable area.

#### Scenario: Rejected draft visible
- **WHEN** the user opens the nested detail of an attempt-1 synthesize row whose evaluation failed
- **THEN** the text of that rejected draft is shown

#### Scenario: Large tool result
- **WHEN** the user opens a tool call whose result is many kilobytes of JSON
- **THEN** the result is shown pretty-printed inside a height-limited scrollable area without stretching the panel

### Requirement: Summary feedback carries the run outcome
Feedback submitted from the AI Summary SHALL include, along with the query and summary, the run's status, path, attempts used, score and the per-stage model mapping. It SHALL NOT include tool results or draft text. A daily usage limit message SHALL NOT offer feedback, because it is not an answer.

#### Scenario: Thumbs down on a limit-reached summary
- **WHEN** the user gives negative feedback on a summary whose run ended `limit_reached` on attempt 2 with score 2
- **THEN** the submitted payload contains status `limit_reached`, the path, attemptsUsed 2, score 2 and the stage-to-model mapping

#### Scenario: No bulky fields
- **WHEN** any AI Summary feedback is submitted
- **THEN** the payload contains no tool call results and no draft text

### Requirement: Test mode can exercise every summary state
In test mode, the summary stream SHALL also offer scripted runs that follow the chat event contract: an `insight` run that fails one evaluation and is then accepted, a `refused` run, an `insight_limit_reached` run, and a `cached` run. Which scripted run plays SHALL be chosen by the query text, with the existing keyword run as the default.

#### Scenario: Insight retry run
- **WHEN** the service is in test mode and the query selects the insight scenario
- **THEN** the stream contains two synthesize and two evaluate steps, the first evaluation failing, and an `accepted` outcome on attempt 2

#### Scenario: Refused run
- **WHEN** the service is in test mode and the query selects the refusal scenario
- **THEN** the stream contains only the classify and refuse steps and a `refused` outcome

#### Scenario: Insight limit run
- **WHEN** the service is in test mode and the query selects the insight limit scenario
- **THEN** the stream contains only the classify, route and limit steps, the fixed insight limit message and an `insight_limit_reached` outcome

#### Scenario: Cached run
- **WHEN** the service is in test mode and the query selects the cached scenario
- **THEN** the stream contains only the cache step, one answer message and a `cached` outcome

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
