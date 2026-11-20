# Spec Delta

## MODIFIED Requirements

### Requirement: Admitted runs count even when they fail
A run SHALL count towards the client and overall caps when it is admitted, whatever its result, including failed, aborted and refused runs. A run answered from the answer cache SHALL NOT count towards any cap.

#### Scenario: Aborted run
- **WHEN** a client aborts a run after it was admitted
- **THEN** that run still counts towards the client and overall caps

#### Scenario: Cached answer
- **WHEN** a client under its cap receives an answer from the cache
- **THEN** the client and overall counts do not change

## ADDED Requirements

### Requirement: Caps are checked before the cache
A request over the client or overall cap SHALL receive HTTP 429 even when its query would be answered from the cache, and the cache SHALL NOT be looked up for it.

#### Scenario: Over-cap client asks a cached query
- **WHEN** a client that has reached its cap posts a query whose answer is cached
- **THEN** the response is HTTP 429 and no cache lookup is made
