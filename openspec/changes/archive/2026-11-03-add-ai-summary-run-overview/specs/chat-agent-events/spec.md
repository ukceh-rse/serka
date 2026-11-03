# Spec Delta

## MODIFIED Requirements

### Requirement: Tool calls are streamed as AG-UI tool call events
Every catalogue tool call, whether chosen by a model or run directly for a `keyword` query, SHALL be streamed inside the `execute` step as `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END` and `TOOL_CALL_RESULT` events sharing one tool call id, with `toolCallName` set to the tool's name. A `TOOL_CALL_RESULT` for a call that did not succeed SHALL have content starting with `Error: `, on both paths.

#### Scenario: Keyword search call
- **WHEN** a `keyword` query runs its planned search
- **THEN** the `execute` step contains one tool call event sequence named after the search tool, with its arguments and result

#### Scenario: Keyword search with a location
- **WHEN** a `keyword` query names a place, such as "river flow Wales"
- **THEN** the `execute` step contains a geocoding tool call sequence followed by the search tool call sequence

#### Scenario: Failed model-chosen tool call
- **WHEN** a tool call chosen by a model fails or is sent back to the model for a retry
- **THEN** its `TOOL_CALL_RESULT` content starts with `Error: `
