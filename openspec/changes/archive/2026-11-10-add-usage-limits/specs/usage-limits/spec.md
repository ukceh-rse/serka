# Spec Delta

## Purpose

Keeps Bedrock spending under a known daily ceiling on public, unauthenticated endpoints, by limiting how many model-backed runs happen and how much text a query can carry, and by controlling whether the chat endpoint is available.

## ADDED Requirements

### Requirement: Runs are capped per client per day
The system SHALL allow each client at most 30 model-backed runs per UTC day, by default. A request over this cap SHALL receive HTTP 429 before any model is called. The limit SHALL be configurable without a code change.

#### Scenario: Client under the cap
- **WHEN** a client that has made 29 runs today posts a valid query to `/v1/chat/stream`
- **THEN** the run starts and the response is an event stream

#### Scenario: Client over the cap
- **WHEN** a client that has made 30 runs today posts a valid query to `/v1/chat/stream`
- **THEN** the response is HTTP 429 and no model is called

#### Scenario: Another client is unaffected
- **WHEN** one client has reached its cap and a different client posts a valid query
- **THEN** the second client's run starts

### Requirement: Runs are capped overall per day
The system SHALL allow at most 500 model-backed runs per UTC day across all clients, by default. A request over this cap SHALL receive HTTP 429 before any model is called. The limit SHALL be configurable without a code change.

#### Scenario: Overall cap reached
- **WHEN** 500 runs have been admitted today and a client under its own cap posts a valid query
- **THEN** the response is HTTP 429 and no model is called

#### Scenario: Client rejection does not use overall allowance
- **WHEN** a client over its own cap is rejected
- **THEN** today's overall count does not change

### Requirement: Limit responses tell the client when to retry
An HTTP 429 from a daily cap SHALL include a `Retry-After` header giving the seconds until the next reset, and a body with a machine-readable code that distinguishes the client cap from the overall cap and a message suitable for showing to a user.

#### Scenario: Retry information
- **WHEN** a request is rejected by a daily cap
- **THEN** the response has a `Retry-After` header counting down to the next midnight UTC, and a body with a code and a message

### Requirement: Admitted runs count even when they fail
A run SHALL count towards the client and overall caps when it is admitted, whatever its result, including failed, aborted and refused runs.

#### Scenario: Aborted run
- **WHEN** a client aborts a run after it was admitted
- **THEN** that run still counts towards the client and overall caps

### Requirement: Daily counts reset at midnight UTC and on restart
All daily counts SHALL be held in memory, and SHALL start again from zero at midnight UTC and when the service restarts.

#### Scenario: Restart
- **WHEN** the service restarts after 200 runs were admitted today
- **THEN** the overall count for today starts again from zero

#### Scenario: New day
- **WHEN** the first request after midnight UTC arrives
- **THEN** all daily counts start from zero

### Requirement: Clients are identified by the address seen by the trusted proxy
The system SHALL identify a client by the address recorded by the outermost trusted proxy, counting back from the right of `X-Forwarded-For` by a configured number of trusted hops. Addresses to the left of that position are client-supplied and SHALL be ignored.

#### Scenario: Spoofed header
- **WHEN** one trusted hop is configured and a request arrives with `X-Forwarded-For: 1.1.1.1, 203.0.113.7, 10.0.0.5`
- **THEN** the client is identified as `203.0.113.7`, whatever value the client supplied on the left

#### Scenario: No trusted proxies
- **WHEN** no trusted hops are configured
- **THEN** `X-Forwarded-For` is ignored and the client is identified by the connecting address

#### Scenario: Header shorter than expected
- **WHEN** `X-Forwarded-For` has too few entries for the configured hops
- **THEN** the client is identified by the connecting address

### Requirement: Client addresses are not kept beyond the day
The system SHALL hold client addresses for the daily caps only in memory, SHALL NOT write them to disk, and SHALL discard them once the day has ended.

#### Scenario: Previous day removed
- **WHEN** the first request of a new UTC day has been handled
- **THEN** no client address from an earlier day remains

### Requirement: Insight runs are capped per day
The system SHALL allow at most 100 `insight` runs per UTC day across all clients, by default. A query classified `insight` over this cap SHALL end before planning, with no further model calls, and SHALL NOT fall back to the keyword path. The limit SHALL be configurable without a code change.

#### Scenario: Insight cap reached
- **WHEN** 100 `insight` runs have started today and another query is classified `insight`
- **THEN** the answer text is exactly the fixed insight limit message
- **AND** no planning, retrieval, composition or evaluation happens

#### Scenario: Keyword runs continue
- **WHEN** the insight cap has been reached and a query is classified `keyword`
- **THEN** the query is processed normally

#### Scenario: Stopped request still counts
- **WHEN** a query is stopped by the insight cap
- **THEN** it still counts towards the client and overall caps, but not towards the insight count

### Requirement: Query length is limited
The system SHALL reject a `message` to `/v1/chat/stream` or a `q` to `/v1/query/semantic` longer than 500 characters with HTTP 422, before any model or search call. It SHALL also reject a blank `message`, or an agui request with no user message, with HTTP 422 before any model call. A rejected query SHALL NOT count towards any daily cap and SHALL NOT be written to the feedback log.

#### Scenario: Query at the limit
- **WHEN** a client posts a `message` of exactly 500 characters
- **THEN** the query is accepted

#### Scenario: Query over the limit
- **WHEN** a client posts a `message` of 501 characters
- **THEN** the response is HTTP 422, no model is called and no daily count changes

#### Scenario: Blank query
- **WHEN** a client posts a `message` that is empty or only whitespace
- **THEN** the response is HTTP 422, no model is called and no daily count changes

#### Scenario: Search query over the limit
- **WHEN** a client requests `/v1/query/semantic` with a `q` of 501 characters
- **THEN** the response is HTTP 422, no search is run and nothing is logged

### Requirement: Search input matches the query limit
The search box SHALL NOT accept more characters than the API's query length limit.

#### Scenario: Typing past the limit
- **WHEN** a user tries to type or paste more than 500 characters into the search box
- **THEN** the input holds only the first 500 characters

### Requirement: Plain search is not capped
Requests to `/v1/query/semantic` SHALL NOT count towards, or be blocked by, any daily cap.

#### Scenario: Search after reaching the caps
- **WHEN** a client has reached its daily cap and requests `/v1/query/semantic` with a valid query
- **THEN** the search runs normally

### Requirement: The chat endpoint is off by default
`/v1/chat/stream/agui` SHALL respond with HTTP 404 unless chat is enabled in configuration, and chat SHALL be disabled by default. `/v1/chat/stream` SHALL stay available either way. When chat is enabled, each request SHALL count towards the client and overall caps, and its latest user message SHALL obey the query length limit.

#### Scenario: Chat disabled
- **WHEN** chat is not enabled and a client posts to `/v1/chat/stream/agui`
- **THEN** the response is HTTP 404 and no model is called

#### Scenario: Chat enabled
- **WHEN** chat is enabled and a client under its caps posts a valid request to `/v1/chat/stream/agui`
- **THEN** the response is an event stream and the run counts towards the caps

#### Scenario: Summary unaffected
- **WHEN** chat is not enabled and a client posts a valid query to `/v1/chat/stream`
- **THEN** the run starts

### Requirement: The UI does not offer chat
The web UI SHALL NOT provide a chat page route while chat is a future feature.

#### Scenario: Visiting the old route
- **WHEN** a user opens `/chat` in the web UI
- **THEN** no chat page is shown and no request is sent to `/v1/chat/stream/agui`

### Requirement: Test mode does not enforce daily caps
When the service runs in test mode, no daily cap SHALL be enforced and no daily counts SHALL be kept. Query length limits SHALL still apply.

#### Scenario: Test mode requests
- **WHEN** `TEST_MODE=true` and a client makes more than 30 requests to `/v1/chat/stream` in a day
- **THEN** every valid request receives an event stream
