# Spec Delta

## MODIFIED Requirements

### Requirement: Keyword queries use a planned search without model-chosen tool calls
For a `keyword` query the system SHALL derive search parameters (terms and any filters such as type, location or dates, and any ordering such as by citations or publication date) and run the catalogue search with them directly, geocoding a named location first. No model SHALL choose tool calls during retrieval.

#### Scenario: Keyword retrieval
- **WHEN** a `keyword` query "nitrogen deposition uplands" is processed
- **THEN** exactly one catalogue search is performed with parameters derived from the query
- **AND** the answer lists the most relevant results returned by that search

#### Scenario: Ranking query
- **WHEN** a `keyword` query "most cited datasets" is processed
- **THEN** exactly one catalogue search is performed, sorted by citations in descending order, with no search terms
- **AND** the answer lists the returned datasets with their citation counts

### Requirement: Insight queries use model-chosen tool calls guided by a plan
For an `insight` query the system SHALL first produce a retrieval plan, then let a model choose and call catalogue tools, possibly several in sequence, to carry out that plan.

#### Scenario: Multi-tool retrieval
- **WHEN** an `insight` query needs a dataset and its contributors
- **THEN** the model may call `search`, then `read` on a concept ID returned by the first call, then `read` on the contributor links in that concept

#### Scenario: Repeated searches
- **WHEN** a first search returns too little to answer the query
- **THEN** the model may call `search` again with different terms or filters

#### Scenario: Aggregate question
- **WHEN** the query "which author contributed to the most datasets?" is processed
- **THEN** it is handled as an `insight` query
- **AND** the model calls `aggregate` grouped by person with the author role, rather than paging through search results

### Requirement: Answers are grounded in retrieved data
Every answer SHALL be composed only from data returned by catalogue tools during the current request, or be a cached answer that was composed that way and accepted. Dataset titles and URIs SHALL be cited exactly as returned. When retrieval returns nothing relevant, the answer SHALL say that no matching datasets were found.

#### Scenario: Citation
- **WHEN** an answer mentions a dataset
- **THEN** it links the dataset's exact returned title to its exact returned URI

#### Scenario: No results
- **WHEN** retrieval returns no relevant results
- **THEN** the answer states that no datasets matching the query were found in the EIDC catalogue

#### Scenario: Counts
- **WHEN** an answer states how many datasets, people or other concepts match
- **THEN** that number was returned by `aggregate` during the request, and the answer says what was counted

#### Scenario: Cached answer
- **WHEN** an answer is returned from the cache
- **THEN** it is the text of an earlier accepted answer, unchanged
