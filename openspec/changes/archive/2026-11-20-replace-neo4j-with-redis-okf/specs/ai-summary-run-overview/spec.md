# Spec Delta

## MODIFIED Requirements

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
