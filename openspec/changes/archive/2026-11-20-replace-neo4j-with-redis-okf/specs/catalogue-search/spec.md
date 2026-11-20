# Spec Delta

## Purpose

Defines how the OKF bundle is indexed in Redis and searched: chunking, hybrid full-text and semantic search, filters, catalogue aggregates, the agent's `search`, `read` and `aggregate` tools, and the plain search endpoint.

## ADDED Requirements

### Requirement: The index is rebuilt from the bundle alone
Loading SHALL read only the local bundle, and SHALL replace the whole Redis search index, the relation index and the stored concepts with the bundle's contents. Loading the same bundle twice SHALL produce the same index.

#### Scenario: Reload
- **WHEN** a bundle is loaded, then edited to remove a dataset, then loaded again
- **THEN** no search, read or aggregate returns or counts the removed dataset

#### Scenario: No source access
- **WHEN** the bundle is loaded with no network access to EIDC or Legilo
- **THEN** loading succeeds, needing only Redis and the embedding model

### Requirement: Every concept file is chunked and searchable
Loading SHALL split the body of every concept file, including supporting documents and ontology concepts, into overlapping chunks. It SHALL index each chunk for full-text and semantic search. A concept whose body is empty SHALL be indexed as one chunk made from its title and description.

#### Scenario: Supporting document text
- **WHEN** a phrase appears only in a supporting PDF's extracted text
- **THEN** a search for that phrase returns a chunk from that document concept

#### Scenario: Ontology concept
- **WHEN** the agent searches for "custodian role"
- **THEN** the results can include the custodian role's ontology concept

#### Scenario: Concept with no body
- **WHEN** a person concept has frontmatter but no body
- **THEN** a search for that person's name returns a chunk for their concept

### Requirement: Search combines full-text and semantic ranking
When `search` is given a query and no sort, it SHALL rank chunks with a single hybrid query that merges full-text (BM25) and vector similarity rankings by reciprocal rank fusion. No separate reranking model SHALL be used. Each result SHALL be one chunk.

#### Scenario: Exact term
- **WHEN** the query is a rare exact term, such as a site code, that appears in one dataset
- **THEN** a chunk from that dataset is among the results even if its embedding is not the closest

#### Scenario: Paraphrase
- **WHEN** the query paraphrases a dataset description without sharing its key words
- **THEN** a chunk from that dataset is among the results

#### Scenario: Several chunks from one concept
- **WHEN** several chunks of one supporting document match
- **THEN** each matching chunk is a separate result

### Requirement: A search hit carries its chunk and concept summary
Each hit SHALL contain the chunk ID, the chunk text, its score, and its concept's ID, `type`, `title`, `description`, `resource` and `tags`, plus the citation count and publication date for datasets. Unsorted hits SHALL be ordered by score, highest first. A hit SHALL NOT contain embeddings. The result SHALL also report the total number of matches.

#### Scenario: Hit shape
- **WHEN** a search returns a chunk from dataset `datasets/abc`
- **THEN** the hit has the chunk ID, text, score, and a concept with id `datasets/abc`, type `dataset`, its title, description, catalogue URI as `resource`, tags, citation count and publication date

#### Scenario: Total matches
- **WHEN** a search with `limit` 5 matches 240 chunks
- **THEN** the result holds 5 hits and reports 240 matches in total

#### Scenario: No matches
- **WHEN** nothing matches the query
- **THEN** `search` returns an empty list, not an error

### Requirement: Search can be filtered
`search` SHALL accept optional filters: concept `type`, theme (by theme concept ID or label, also matching narrower themes), a linked concept ID, a bounding box, published-after and published-before dates, and a minimum citation count. Filters SHALL apply to both the full-text and the semantic side of the query.

#### Scenario: Type filter
- **WHEN** `search` is called with type `person`
- **THEN** every hit's concept has type `person`

#### Scenario: Broader theme
- **WHEN** `search` is called with the theme "Biodiversity"
- **THEN** hits include datasets whose only theme is the narrower "Freshwater fish"

#### Scenario: Linked concept
- **WHEN** `search` is called with the linked concept `people/xyz`
- **THEN** every hit comes from a concept whose body links `/people/xyz`

#### Scenario: Bounding box
- **WHEN** `search` is called with a bounding box around Windermere
- **THEN** every hit comes from a dataset whose bounding box overlaps that box, expanded by about 20%

#### Scenario: Filter on both sides
- **WHEN** `search` is called with a type filter and a query whose nearest vectors are all of another type
- **THEN** no hit has the other type

### Requirement: Search can sort concepts by citations or publication date
`search` SHALL accept an optional `sort_by` of `citations` or `published` and an `order` (default descending), with the query optional. A sorted search SHALL return one hit per concept, holding the concept's first chunk. Without a query, it SHALL sort every concept matching the filters. With a query, it SHALL sort the most relevant hybrid results.

#### Scenario: Most cited dataset
- **WHEN** `search` is called with no query, type `dataset`, `sort_by` `citations` and `limit` 1
- **THEN** it returns the dataset with the highest citation count in the whole index, in a single call

#### Scenario: Sort with filters
- **WHEN** `search` is called with no query, the theme "Freshwater", `published_after` 2015-01-01 and `sort_by` `citations`
- **THEN** hits are freshwater datasets published since 2015, ordered by citation count, highest first

#### Scenario: One hit per concept
- **WHEN** a sorted search matches a dataset with many chunks
- **THEN** that dataset appears once in the hits

#### Scenario: Sort with a query
- **WHEN** `search` is called with the query "soil carbon" and `sort_by` `citations`
- **THEN** the hits are drawn from the most relevant results for "soil carbon" and ordered by citation count

#### Scenario: Oldest first
- **WHEN** `search` is called with no query, `sort_by` `published` and `order` ascending
- **THEN** hits are ordered by publication date, earliest first

#### Scenario: No query and no sort
- **WHEN** `search` is called with neither a query nor `sort_by`
- **THEN** the tool returns an error saying one of them is required

### Requirement: Aggregate counts matching concepts exactly
`aggregate` SHALL count concepts over the whole index in one call and return exact numbers, accepting the same filters as `search`. Without `group_by` it SHALL return the number of matching concepts of the given `type` (default `dataset`) and, for datasets, their summed citations. An optional `query` SHALL count datasets with a full-text match in the dataset or any of its supporting documents, each dataset once.

#### Scenario: Total datasets
- **WHEN** `aggregate` is called with no arguments on an index of 100 datasets
- **THEN** it returns a total of 100

#### Scenario: Mentions in a supporting document
- **WHEN** `aggregate` is called with `query` "ozone", and one dataset mentions ozone only in two of its supporting documents
- **THEN** that dataset is counted once in the total

### Requirement: Aggregate groups datasets by related concept
With `group_by` of `person`, `organisation`, `grant`, `funder` or `theme`, `aggregate` SHALL return the related concepts with the number of distinct matching datasets for each and their summed citations. Groups SHALL be ordered by `sort_by` (`datasets` by default, or `citations`) and then by title, and the result SHALL report the total number of groups. An optional `role` SHALL restrict `person` and `organisation` groups to contributors with that role.

#### Scenario: Top author
- **WHEN** `aggregate` is called with `group_by` `person`, `role` `author` and `limit` 1
- **THEN** it returns the person who is an author of the most datasets, with that number of datasets

#### Scenario: Most cited author
- **WHEN** `aggregate` is called with `group_by` `person`, `role` `author` and `sort_by` `citations`
- **THEN** people are ordered by the summed citation counts of the datasets they authored, highest first

#### Scenario: Two roles on one dataset
- **WHEN** a person is both author and contact for a dataset, and contributes to no other dataset
- **THEN** a `person` group with no `role` counts them for 1 dataset

#### Scenario: Grouped with filters
- **WHEN** `aggregate` is called with `group_by` `funder`, the theme "Freshwater" and `published_after` 2015-01-01
- **THEN** each funder's count includes only freshwater datasets published since 2015

#### Scenario: Broader theme counts
- **WHEN** `aggregate` is called with `group_by` `theme`
- **THEN** a broader theme's count includes the datasets whose themes are narrower than it

#### Scenario: Query with a relation group
- **WHEN** `aggregate` is called with `query` "soil" and `group_by` `person`
- **THEN** it returns no groups and a warning suggesting a theme filter instead

#### Scenario: Unknown role
- **WHEN** `aggregate` is called with `group_by` `person` and a `role` that no dataset uses
- **THEN** the tool returns an error listing the roles in use

### Requirement: Aggregate counts by year and by type
With `group_by` `year`, `aggregate` SHALL count matching datasets per publication year, ordered by year. With `group_by` `type`, it SHALL count the concepts of each type in the index.

#### Scenario: Per year
- **WHEN** `aggregate` is called with `group_by` `year`
- **THEN** it returns one group per publication year with the number of datasets published that year, the counts adding up to the number of datasets with a publication date

#### Scenario: Catalogue overview
- **WHEN** `aggregate` is called with `group_by` `type`
- **THEN** it returns the number of concepts of each type in the index

### Requirement: Dataset-only filters are reported
The theme, bounding box, date and citation filters SHALL match only chunks of datasets and of their supporting documents, using the dataset's values. When one of them is used with a `type` other than `dataset` or `document`, `search` and `aggregate` SHALL return no hits or counts and a warning that names the filter.

#### Scenario: Supporting document inherits dataset values
- **WHEN** `search` is called with a bounding box that overlaps dataset `abc`
- **THEN** chunks of `abc`'s supporting documents can be returned as well as chunks of `abc`

#### Scenario: Bounding box with person type
- **WHEN** `search` is called with type `person` and a bounding box
- **THEN** it returns no hits and a warning that the bounding box only matches datasets

### Requirement: The agent can read whole concepts
`read` SHALL return the full markdown file (frontmatter and body) for a concept ID or an index path. It SHALL accept IDs with or without a leading `/` and without `.md`. An unknown ID SHALL return a tool error naming the ID.

#### Scenario: Follow a link
- **WHEN** a hit's chunk contains the link `/people/xyz` and the agent calls `read` with `/people/xyz`
- **THEN** it receives that person's concept file

#### Scenario: Read an index
- **WHEN** the agent calls `read` with `ontology/index`
- **THEN** it receives the ontology index

#### Scenario: Unknown concept
- **WHEN** `read` is called with `datasets/does-not-exist`
- **THEN** the tool returns an error naming `datasets/does-not-exist`

### Requirement: The catalogue tools are search, read, aggregate and geocode
The MCP server SHALL offer the tools `search`, `read`, `aggregate` and `geocode_location`, and no others. Tool results SHALL NOT be JSON-LD.

#### Scenario: Tool list
- **WHEN** a client lists the MCP server's tools
- **THEN** the list is exactly `search`, `read`, `aggregate` and `geocode_location`

### Requirement: Plain search returns search hits
`/v1/query/semantic` SHALL return the `search` hits for its query unchanged. It SHALL accept `q`, an optional OKF `type`, a `location` (geocoded to a bounding box), and published-after and published-before dates. An unknown location SHALL return HTTP 422.

#### Scenario: Plain search
- **WHEN** a client requests `/v1/query/semantic?q=pike+windermere`
- **THEN** the response is a JSON list of hits in the same shape that `search` returns

#### Scenario: Type filter
- **WHEN** a client requests `/v1/query/semantic?q=pike&type=dataset`
- **THEN** every hit's concept has type `dataset`

#### Scenario: Unknown location
- **WHEN** a client requests `/v1/query/semantic?q=fish&location=Nowhereville`
- **THEN** the response is HTTP 422
