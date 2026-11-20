# Spec Delta

## Purpose

Saves model calls and time by reusing accepted AI Summary answers for queries that mean the same thing, without ever serving an answer for a different question or for content that has since changed.

## ADDED Requirements

### Requirement: Accepted first-turn answers are cached
After a run with no conversation history ends with outcome `accepted`, the system SHALL store its query, final answer text, path, score and answer model in the semantic cache. Runs with any other outcome, runs with history, and runs in test mode SHALL NOT be stored.

#### Scenario: Accepted run
- **WHEN** a first-turn query ends `accepted`
- **THEN** its answer is stored in the cache

#### Scenario: Limit reached
- **WHEN** a first-turn query ends `limit_reached`
- **THEN** nothing is stored

#### Scenario: Follow-up turn
- **WHEN** a query with earlier conversation turns ends `accepted`
- **THEN** nothing is stored

### Requirement: Similar first-turn queries are answered from the cache
Before classification, the system SHALL look up a query with no conversation history in the semantic cache. If a stored query is within the configured similarity threshold, the system SHALL return that stored answer without calling any chat stage model or catalogue tool.

#### Scenario: Paraphrased query
- **WHEN** "pike in Windermere" was answered and accepted, and a client asks "are there pike in Lake Windermere?"
- **THEN** the stored answer is returned and no classify, plan, execute, synthesize or evaluate stage runs

#### Scenario: Different question
- **WHEN** a stored query is outside the similarity threshold of the new query
- **THEN** the full pipeline runs

#### Scenario: Follow-up turn
- **WHEN** a query arrives with earlier conversation turns
- **THEN** the cache is not looked up

### Requirement: The cache is cleared when the index is reloaded
Loading a bundle into the search index SHALL clear every cached answer.

#### Scenario: Reload
- **WHEN** a bundle is loaded after answers were cached
- **THEN** the next query runs the full pipeline

### Requirement: Cache matching and expiry are configurable
The similarity threshold and the time to live of cached answers SHALL be configurable without a code change. The defaults SHALL favour a miss over a wrong match.

#### Scenario: Expired entry
- **WHEN** a cached answer is older than the configured time to live
- **THEN** it is not returned

### Requirement: Cache failures do not fail runs
If the cache cannot be read or written, the run SHALL continue as if the cache missed, and the failure SHALL be logged.

#### Scenario: Cache unavailable
- **WHEN** the cache lookup raises an error
- **THEN** the full pipeline runs and the run's outcome is unaffected
