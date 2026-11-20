# Tasks

## 1. Setup and FT.HYBRID spike

- [x] 1.1 Add `redis` and `redisvl` to the root and `mcp-server` `pyproject.toml` files, and verify `uv sync` succeeds and both import
- [x] 1.2 Add a `redis:8.10.3` service with a named volume to `compose.yaml`, next to Neo4j for now, and verify `docker compose up redis` answers `PING` and `MODULE LIST`/`FT._LIST` work
- [x] 1.3 Add `redis_url`, `okf_bundle_dir` (default `./bundle`) and the `answer_cache_*` settings to `src/serka/settings.py` and `.env.example`, add `bundle/` to `.gitignore`, and verify `tests/test_settings.py` covers the defaults
- [x] 1.4 Spike: against the local Redis, run `FT.HYBRID` with `COMBINE RRF`, a filter in both `SEARCH` and `VSIM FILTER`, `LOAD`, `LIMIT`, and a `SORTBY` after `COMBINE`, first through RedisVL `HybridQuery`, then redis-py, then `execute_command`. Record which client works for every mode in the design's hybrid search section, and verify with a throwaway script output pasted into the task notes

  Spike output (5 chunks: `a#0`/`a#1` dataset "pike", `b#0` dataset 50 citations, `c#0` person near the query vector, `d#0` dataset; filter `@type:{dataset}`):
  ```
  redisvl HybridQuery (RRF, filter, LOAD, LIMIT): ok, 3 dataset hits; K is num_results
  redisvl HybridQuery stopword-only text: ValueError: text string cannot be empty after removing stopwords
  redis-py hybrid_search (RRF, filter both sides, LOAD, LIMIT): total=4, 3 dataset hits, person excluded
  redis-py hybrid_search + SORTBY after COMBINE: citations 50, 10, 10
  redis-py lead-only + SORTBY: total=3, citations 50, 10, 3 (one per concept)
  execute_command FT.HYBRID + SORTBY: total_results=4, citations 50, 10, 10
  FT.SEARCH "@lead:[1 1] @type:{dataset}" SORTBY citations DESC: total=3, b#0 then a#0
  match-all "* @type:{dataset}": SEARCH_SYNTAX; "@type:{dataset}" alone: ok
  LOAD @__key @__score: ok; LOAD of a YIELD_SCORE_AS alias: SEARCH_FIELD_DUP
  "(pike": SEARCH_SYNTAX Syntax error at offset 1
  ```
  Chosen client: redis-py `ft().hybrid_search`.

## 2. OKF bundle writer

- [x] 2.1 Add concept ID derivation (EIDC ID, ORCID or ROR, otherwise a 12-character hash of the URI, and a document ID from `source_id`) with unit tests for stability and for same-named supporting files
- [x] 2.2 Implement rendering of dataset, person, organisation, grant, theme and document concepts (frontmatter with `type`, `title`, `description`, `resource`, `tags` and the dataset extension keys, plus a body with contributor, related, funding, supporting-document and "Cited by" sections) from `EntityExtractor`/`ConceptHierarchyFetcher` output. Verify with unit tests on `tests/data/eidc-1c2fe14e.json` and `eidc-ae02f4e8.json`
- [x] 2.3 Add theme ancestor expansion into each dataset's `themes` key and broader links on theme concepts, and verify a unit test with a two-level hierarchy
- [x] 2.4 Generate `ontology/` concepts for only the types, roles and predicates used, from `src/serka/doo_mapping.json` definitions, linked from role and predicate text in concept bodies. Reduce `src/serka/ontology.py` to what ingest needs. Verify unit tests for a used role, an unused predicate, and link targets resolving to written files
- [x] 2.5 Write `index.md` at the root (with `okf_version: "0.2"`) and per top-level directory, and verify a conformance test: every non-reserved `.md` has frontmatter with a non-empty `type`, and every bundle-relative link in index files resolves
- [x] 2.6 Replace `Neo4jGraphWriter` in `src/serka/pipelines.py` with the OKF writer component. Have it build into a temporary sibling directory and rename it over `okf_bundle_dir`, and remove the node embedder, document embedder and `TextExtractor` from the ingest pipeline. Verify a pipeline test that a second smaller run leaves only its own concepts and that a failed run leaves the previous bundle intact
- [x] 2.7 Update `scripts/ingest-data.py` (bundle settings, `--no-load`, help text warning that a subset replaces the bundle), and the README "Ingest Data" section. Verify by running `uv run scripts/ingest-data.py 3 --no-load` and inspecting the bundle

## 3. Bundle loader and Redis index

- [x] 3.1 Implement bundle parsing (frontmatter, body, outgoing bundle-relative links normalised to concept IDs) with unit tests, including broken links and links with and without a leading `/`
- [x] 3.2 Implement chunking (word 150/50, title-prefixed embedding text, a single title-plus-description chunk for empty bodies, `lead` on the first chunk), and copy concept and dataset fields onto each chunk, including dataset fields onto its documents' chunks. Verify with unit tests
- [x] 3.3 Implement index creation (`idx:chunks` schema from the design, vector dimension from the embedding model), drop-and-rebuild loading of `chunk:*`, `concept:*` and `theme-label:*` keys, embedding through `CachedDocumentEmbedder`, and clearing the answer cache. Verify an integration test against the local Redis: loading twice gives identical key counts, and removing a dataset then reloading removes its keys
- [x] 3.4 Add `scripts/load-bundle.py` and call it from `ingest-data.py` unless `--no-load` is given. Verify loading an existing bundle with no network access except Redis and Bedrock, and document both commands in the README

## 4. Search module

- [x] 4.1 Implement filter expression building (type, theme ID or label, linked concept, expanded bounding box overlap, dates as epoch days, minimum citations, `lead`) with query-text escaping and a match-all fallback for empty text, and verify with unit tests on the generated expressions
- [x] 4.2 Implement hybrid search (`FT.HYBRID` with RRF, `window = max(20, 2 * limit)`, filters on both sides, one hit per chunk, `total`), using the client chosen in 1.4. Verify integration tests: exact rare term, paraphrase, several chunks from one document, type filter on both sides, and no matches returns an empty list
- [x] 4.3 Implement sorted search: no query uses `FT.SEARCH` with `@lead:[1 1]` and `SORTBY`; query plus sort uses `FT.HYBRID` on lead chunks with a window of `max(50, 5 * limit)` then `SORTBY`. Verify integration tests for most cited dataset, sort with theme and date filters, one hit per concept, ascending published, and an error when there is neither query nor sort
- [x] 4.4 Implement warnings for dataset-only filters used with a non-dataset type (no hits), `sort_by` with a non-dataset type, and full-text syntax errors (retried as vector-only). Verify unit tests for each warning
- [x] 4.5 Implement `read(id)` normalisation (leading `/`, `.md`, index paths) and an unknown-ID error. Verify integration tests for a concept, `ontology/index` and an unknown ID

## 5. MCP server

- [x] 5.1 Rewrite `mcp-server/src/serka-mcp/tools.py` to expose exactly `search`, `read` and `geocode_location` with the design's signatures, descriptions (including the theme-versus-relevance-window guidance and what `total` counts) and plain JSON results. Verify `tests/test_mcp_server.py` lists exactly these tools and checks the hit shape
- [x] 5.2 Update `app.py` to use one Redis client and the Bedrock embedder, and delete `queries.py`, `entities.py`, `ontology.py`, the DOO models in `models.py`, `doo_mapping.json`, the `doo://` resources, the cross-encoder and `RERANKING_ENABLED`. Verify the MCP image builds without `sentence-transformers`, and the server starts against the local Redis
- [x] 5.3 Update `mcp-server/README.md` for the new tools and environment, and verify the documented run command works

## 6. API search endpoint

- [x] 6.1 Change `/v1/query/semantic` to take `q`, `type`, `location`, `published_after` and `published_before`, and to return the `search` hits unchanged (dropping `return_type`, `hops` and `ReturnType`). Keep the 500-character limit and the 422 on an unknown location. Verify `tests/test_app.py` cases for the hit shape, the type filter and an unknown location
- [x] 6.2 Update the test-mode mock search in `src/serka/routers/mock.py` to return OKF chunk hits, including several chunks for one concept and a document hit, and verify `tests/test_app.py` test-mode search cases

## 7. Chat pipeline retrieval

- [x] 7.1 Add optional `sort_by` and `order` to the keyword plan output, make terms optional, and pass them to the direct `search` call. Add "most cited" and "latest" examples to the plan-keyword prompt. Verify a `tests/test_chat_pipeline.py` case where "most cited datasets" makes one sorted search with no terms
- [x] 7.2 Update `src/serka/prompts.py` tool descriptions for `search`/`read`, `read("ontology/index")`, link following and repeated searches, and replace JSON-LD unwrapping in `render_tool_results` with hit rendering. Verify updated pipeline tests, including the multi-tool test now calling `search` then `read`
- [x] 7.3 Update the "Chat Pipeline" README section for the new tools, and verify it names no removed tool

## 8. Answer cache

- [x] 8.1 Implement `src/serka/answer_cache.py` (`lookup`, `store`, `clear` over RedisVL `SemanticCache` with the Bedrock vectorizer, the configured threshold and TTL, and errors logged and treated as misses). Verify unit tests with a fake backend for hit, miss, expiry passthrough and an error-as-miss
- [x] 8.2 Split the usage limiter into a check-only call at admission and a count call after a cache miss, so over-cap requests get 429 with no lookup and hits are never counted. Verify `tests/test_usage.py` and `tests/test_chat_api.py` cases for an over-cap client with a cached query, and for an under-cap hit leaving counts unchanged
- [x] 8.3 Add the `cache` step before `classify` for first-turn queries, emit a cached run (`RUN_METADATA` with the stored model, one text message, `serka.outcome` status `cached` with the stored path and score), and store only accepted first-turn answers outside test mode. Verify `tests/test_chat_events.py` and `tests/test_chat_pipeline.py` for the hit steps, the miss steps, follow-up turns bypassing the cache, and `limit_reached` not being stored
- [x] 8.4 Add a scripted `cached` run to the test-mode mock stream, chosen by query text, and verify a `tests/test_app.py` case that it contains only the cache step, one answer message and a `cached` outcome
- [x] 8.5 Document the cache settings and the LangCache swap point in the README "Usage Limits" section or a new "Answer Cache" section, and verify the documented settings match `settings.py`

## 9. Results page

- [x] 9.1 Update `ui/src/api/search.ts` and `ui/src/stores/searchStore.ts` for the hit shape and `type` parameter, and derive groups (bucketed by concept ID, ordered by best score, hits in score order). Verify vitest unit tests for grouping order
- [x] 9.2 Add `ConceptResultCard` (type, title linked to `resource`, description, best passage, an "N more passages" expander, and a dataset link for documents), and replace `EntityResultCard`, `DatasetResultCard` and `RelationshipPanel` on `ResultsPage.tsx`. Verify component tests for a single hit, a collapsed group and a document group
- [x] 9.3 Replace `typeMeta.tsx` and `TypeChip.tsx` DOO types with OKF types and a generic fallback, point the type filter at `type`, and delete `ui/src/ontology.ts` and `ui/src/doo_mapping.json`. Verify `npm run lint`, `npm test` and a test for an unknown type
- [x] 9.4 Add the `cached` summary row to `RunOverview.tsx` and `ui/src/run/runTrace.ts` (saved answer to a similar question, with path and score, and no attempt or tool counts), and make feedback include status `cached`. Verify `runTrace.test.ts` cases
- [x] 9.5 Run the UI against the test-mode API, and verify grouped results, the type filter and the scripted cached summary render correctly

## 10. Remove Neo4j

- [x] 10.1 Delete `src/serka/graph/writers.py`, `src/serka/graph/models.py`, `tests/test_writers.py`, `scripts/sync-doo-mapping.py` and the `neo4j_*` settings, and remove `neomodel` and `neo4j-haystack` from dependencies. Verify `grep -ri neo4j src mcp-server/src tests scripts ui/src` finds nothing, and that `uv run pytest -m "not integration"`, `ty check` (which replaces mypy) and `ruff` pass
- [x] 10.2 Remove the `neo4j` service and `NEO4J_*` env from `compose.yaml`, add `REDIS_URL` and `depends_on: redis` for `serka` and `mcp`, and replace the Neo4j env and directories in `terraform/scripts/setup.sh` with Redis ones. Verify `docker compose config` is valid and `docker compose up` starts all services
- [x] 10.3 Update `README.md`, `CONTRIBUTING.md` and `.env.example` to remove Neo4j and describe Redis, the bundle and the load step. Verify no document mentions Neo4j, Cypher or the removed tools

## 11. Integration checks

- [x] 11.1 Rewrite `scripts/smoke-test.py` for the new stack (ingest `tests/smoke/datasets.txt`, load, then check `search`, sorted search, `read`, `/v1/query/semantic`, a keyword and an insight summary, and a cached repeat). Verify it passes against `docker compose up` with Bedrock access
- [x] 11.2 Compare smoke-test query results with the previous Neo4j and cross-encoder ranking (from a checkout of `main`), record the differences and any RRF `WINDOW`/`CONSTANT` or cache threshold changes in the design's Open Questions, and verify every expected dataset in the smoke checks still ranks in the top `limit`

## 12. Aggregate questions

- [x] 12.1 Write `contributors` (`[{id, roles}]` with `ontology/roles/` names), `grants` and `funders` into dataset frontmatter from the same extractor output as the body sections. Verify writer unit tests on `tests/data/eidc-1c2fe14e.json`: a person with two roles, a funder reached through a grant, and every frontmatter relation also linked in the body
- [x] 12.2 Add the `dataset` field to every chunk (the dataset's ID on its own chunks and its documents' chunks) and to the `idx:chunks` schema. Verify `tests/test_okf_chunks.py` cases for a dataset chunk, a document chunk and a person chunk (no field)
- [x] 12.3 Write `rel:<dataset-id>#<n>` records (one per dataset and related concept, kinds `person`, `organisation`, `grant`, `funder` and `theme`, with roles and the dataset's filter fields) and create `idx:relations` in the loader's drop-and-rebuild. Verify the loader integration test: key counts are identical across two loads, a removed dataset's relation records are gone, and a two-role contributor has one record
- [x] 12.4 Implement `aggregate` in `mcp-server/src/serka-mcp/catalogue.py`: a total with summed citations, a full-text `query` counted by distinct `dataset`, `year` and `type` groups on `idx:chunks`, and relation groups on `idx:relations` with `role`, `sort_by` (`datasets` or `citations`, ties by title), `limit` and `total_groups`, reusing the `search` filter-expression builder. Verify integration tests for each scenario in the three catalogue-search aggregate requirements, including that grouped counts match `@links` filter counts
- [x] 12.5 Add the `aggregate` warnings and errors (dataset-only filters with another type, `query` with a relation group, `role` without a person or organisation group, an unknown role listing the roles in use). Verify unit tests with the stub catalogue in `tests/test_catalogue.py`
- [x] 12.6 Expose `aggregate` in `tools.py`, with a description saying what each count means (distinct datasets, ancestors included for themes, matches rather than similarity for `query`), point `search`'s `total` description at it, and update the tool-list test to the four tools. Verify `tests/test_mcp_server.py`
- [x] 12.7 Add aggregate examples to the classifier (as `insight`) and the insight plan prompt, replace the answer prompt's "do not claim specific counts" rule with the rule to state only counts returned by `aggregate` and what they count, and render aggregate results in `render_tool_results`. Verify a `tests/test_chat_pipeline.py` case where "which author contributed to the most datasets?" is classified `insight` and calls `aggregate` with `group_by` `person` and `role` `author`
- [x] 12.8 Add aggregate checks ("how many datasets are there?" and the top author, compared with counts from `@links` filters) to `scripts/smoke-test.py`, and describe `aggregate` in `mcp-server/README.md` and the README "Chat Pipeline" section. Verify the smoke test passes against the 100-dataset test bundle

## Workflow follow-up

- Verify the change with `/opsx:verify` before archiving.
- Archive the change and sync its specs with `/opsx:archive` once review is complete.
