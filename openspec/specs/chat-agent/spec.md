# chat-agent Specification

## Purpose

Defines how the EIDC chat assistant handles a user query: deciding whether it is in scope, choosing how much effort to spend, retrieving catalogue data, checking its own answer, and telling the user when it is not confident in that answer.

## Requirements

### Requirement: Out-of-scope queries are refused with a fixed message
The system SHALL classify every query as in scope (environmental science or the EIDC catalogue) or out of scope before doing any retrieval. Out-of-scope queries SHALL receive exactly the fixed refusal message "This tool is only able to search the EIDC catalogue and help you find datasets. I'm afraid I cannot help with that request." with no tool calls and no generated text.

#### Scenario: Off-topic request
- **WHEN** a user asks "write me a Python function to sort a list"
- **THEN** the response text is exactly the fixed refusal message
- **AND** no catalogue tools are called

#### Scenario: In-scope request is not refused
- **WHEN** a user asks "what datasets cover soil carbon in UK uplands?"
- **THEN** the query proceeds to retrieval and the refusal message is not returned

### Requirement: Classification uses the conversation context
When a conversation history is supplied, the system SHALL classify the latest user message in the context of the earlier messages, so short follow-ups to an in-scope conversation are treated as in scope.

#### Scenario: Follow-up question
- **WHEN** the history contains an in-scope question about river flow datasets and the latest message is "what about in Wales?"
- **THEN** the latest message is classified as in scope

### Requirement: In-scope queries are labelled keyword or insight
The system SHALL label each in-scope query as either `keyword` (the user wants to find datasets or entities matching some terms) or `insight` (the user asks a question that needs reasoning across retrieved information). The label SHALL determine the attempt limit and how tools are chosen.

#### Scenario: Keyword query
- **WHEN** a user sends "bat habitat woodland"
- **THEN** the query is labelled `keyword`

#### Scenario: Insight query
- **WHEN** a user asks "how has monitoring of freshwater invertebrates in the River Wye changed since 2015, and who funded it?"
- **THEN** the query is labelled `insight`

### Requirement: Keyword queries use a planned search without model-chosen tool calls
For a `keyword` query the system SHALL derive search parameters (terms and any filters such as type, location or dates) and run the catalogue search with them directly, geocoding a named location first. No model SHALL choose tool calls during retrieval.

#### Scenario: Keyword retrieval
- **WHEN** a `keyword` query "nitrogen deposition uplands" is processed
- **THEN** exactly one catalogue search is performed with parameters derived from the query
- **AND** the answer lists the most relevant results returned by that search

### Requirement: Insight queries use model-chosen tool calls guided by a plan
For an `insight` query the system SHALL first produce a retrieval plan, then let a model choose and call catalogue tools, possibly several in sequence, to carry out that plan.

#### Scenario: Multi-tool retrieval
- **WHEN** an `insight` query needs a dataset and its contributors
- **THEN** the model may call a search tool and then a related-entity tool using values returned by the first call

### Requirement: Answers are grounded in retrieved data
Every answer SHALL be composed only from data returned by catalogue tools during the current request. Dataset titles and URIs SHALL be cited exactly as returned. When retrieval returns nothing relevant, the answer SHALL say that no matching datasets were found.

#### Scenario: Citation
- **WHEN** an answer mentions a dataset
- **THEN** it links the dataset's exact returned title to its exact returned URI

#### Scenario: No results
- **WHEN** retrieval returns no relevant results
- **THEN** the answer states that no datasets matching the query were found in the EIDC catalogue

### Requirement: Every answer is evaluated against the query
After composing an answer, the system SHALL evaluate it against the query. The evaluation SHALL produce a pass/fail verdict, a score from 1 to 5, a problem category (`none`, `data` or `writing`), and short feedback.

#### Scenario: Evaluation recorded
- **WHEN** an answer is composed for any in-scope query
- **THEN** an evaluation with verdict, score, problem category and feedback is produced for it

### Requirement: Attempt limits depend on the query label
A `keyword` query SHALL be processed in exactly one attempt. An `insight` query SHALL be processed in at most 3 attempts in total. When an evaluation fails and attempts remain, the system SHALL retry: from planning when the problem is `data`, or from answer composition when the problem is `writing`, using the evaluation feedback.

#### Scenario: Keyword query fails evaluation
- **WHEN** the single attempt for a `keyword` query fails evaluation
- **THEN** no retry happens

#### Scenario: Insight data problem
- **WHEN** attempt 1 of an `insight` query fails evaluation with problem `data`
- **THEN** attempt 2 starts from planning and receives the evaluation feedback

#### Scenario: Insight writing problem
- **WHEN** an `insight` attempt fails evaluation with problem `writing`
- **THEN** the next attempt re-composes the answer from the already retrieved data without new retrieval

#### Scenario: Insight limit
- **WHEN** 3 attempts of an `insight` query have all failed evaluation
- **THEN** no fourth attempt happens

### Requirement: Incomplete answers are returned and flagged
When the attempt limit is reached without a passing evaluation, the system SHALL return the highest-scoring answer from all attempts, end its text with the fixed note "Note: this answer may be incomplete. The system's quality check wasn't fully satisfied.", and report the outcome as `limit_reached` with the evaluation feedback.

#### Scenario: Best draft returned
- **WHEN** an `insight` query's three attempts score 3, 2 and 2 and all fail
- **THEN** the answer from the first attempt is returned, followed by the fixed note

#### Scenario: Passing answer is not flagged
- **WHEN** an attempt passes evaluation
- **THEN** that answer is returned without the note and the outcome is `accepted`

### Requirement: Models are configured per stage on Bedrock in eu-west-2
Each model-backed stage SHALL use a model configured for that stage, independently of the others, through environment configuration. All model calls SHALL be made to Amazon Bedrock in the `eu-west-2` region. The same stage SHALL use the same model on every attempt.

#### Scenario: Swapping a stage model
- **WHEN** the configured model for evaluation is changed and the service restarts
- **THEN** evaluation uses the new model and all other stages are unchanged

#### Scenario: No escalation on retry
- **WHEN** an `insight` query is retried
- **THEN** each stage uses the same model it used on the first attempt
