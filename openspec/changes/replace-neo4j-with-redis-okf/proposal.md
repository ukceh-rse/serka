# Proposal

## Why

Serka keeps the EIDC catalogue as a Neo4j property graph described by the DOO ontology, and every layer (Cypher queries, MCP tools, the API and the UI) is built around typed graph semantics and JSON-LD. That makes the system heavy to run and to change, while the agent mostly needs to find passages and read documents. We want the catalogue as plain, agent-readable knowledge in the Open Knowledge Format (OKF), served from Redis with full-text and semantic search, so agents can search several times and read whole documents instead of walking a graph.

## What Changes

- **BREAKING**: remove Neo4j completely: the compose service, terraform setup, settings, the `neomodel` and `neo4j-haystack` dependencies, the graph writer and node models, and every Cypher query.
- Ingest writes a local OKF v0.2 bundle: one markdown concept per dataset, person, organisation, grant, theme and supporting document, linked by bundle-relative markdown links. The bundle also contains `ontology/` concepts generated from DOO, which describe the bundle's types, contributor roles and relation predicates. Storing the bundle elsewhere (a repo or object store) is later work.
- A loader reads the bundle into Redis Open Source 8.10. It chunks and embeds every concept file, and indexes the chunks for full-text, vector, tag, numeric and link filtering. Redis is an index that can be rebuilt from the bundle at any time.
- Search uses Redis `FT.HYBRID`, which merges BM25 and vector results with reciprocal rank fusion. **BREAKING**: the cross-encoder reranker and the separate vector and full-text queries are removed.
- **BREAKING**: the MCP tool surface shrinks to `search` (one hit per chunk, or one per concept when sorting by citations or publication date for questions like "most cited dataset"), `read` (a whole concept file), `aggregate` and `geocode_location`.
- Add `aggregate` for counting and ranking questions over the whole catalogue, such as "how many datasets are there?", "which author contributed to the most datasets?" or "how many datasets were published each year?". It returns exact counts and citation sums, optionally grouped by person, organisation, grant, funder, theme, year or type, with the same filters as `search`. It reads a second Redis index with one record per dataset relation, because Redis cannot group correctly on multi-value fields. Dataset frontmatter gains `contributors`, `grants` and `funders` keys to feed it. `get_entity`, `get_relations`, `get_contributors`, `find_by_contributor`, `list_datasets`, `get_content`, `describe_ontology` and the `doo://` resources are removed. Tool results are no longer JSON-LD.
- **BREAKING**: `/v1/query/semantic` returns the `search` chunk hits, each carrying a summary of its OKF concept. `return_type` becomes an OKF `type` filter and `hops` is removed. The endpoint is expected to be retired later.
- The Results page groups chunk hits by concept on the client: the most relevant passage is shown and the rest are collapsed. DOO type metadata in the UI is replaced by OKF types.
- Add a semantic answer cache: the RedisVL `SemanticCache` on the same Redis instance stores accepted first-turn AI Summary answers and returns them for near-identical queries. It can be swapped for Redis LangCache when that can run locally.
- A cache hit is streamed as its own short run with a new `cached` outcome. It does not use daily allowance.

## Capabilities

### New Capabilities
- `okf-bundle`: the local OKF bundle that ingest produces: layout, concept types, frontmatter, links, generated ontology concepts and index files.
- `catalogue-search`: loading the bundle into Redis, chunking and embedding, hybrid search and filters, catalogue aggregates, the `search`, `read` and `aggregate` MCP tools, and the `/v1/query/semantic` response.
- `search-results`: how the Results page groups and shows chunk hits by concept.
- `answer-cache`: semantic caching of AI Summary answers: what is stored, when it is looked up, and when it is cleared.

### Modified Capabilities
- `chat-agent`: a cached answer may be returned without retrieval; insight retrieval uses the `search`, `read` and `aggregate` tools, and answers may state counts that `aggregate` returned.
- `chat-agent-events`: a `cache` step and a `cached` outcome status.
- `usage-limits`: cache hits do not count towards daily caps.
- `ai-summary-run-overview`: a cached summary row, and a scripted cached run in test mode.

## Impact

- **Services**: Neo4j is removed and Redis 8.10 is added (`compose.yaml`, `terraform/`). The MCP container connects to Redis only, and no longer loads the ONNX cross-encoder.
- **Code removed**: `src/serka/graph/writers.py`, `src/serka/graph/models.py`, the `mcp-server/` and `ui/src/` copies of `doo_mapping.json`, `scripts/sync-doo-mapping.py`, `mcp-server/src/serka-mcp/queries.py`, `entities.py`, `ontology.py`, and most of `models.py` and `tools.py`. `src/serka/doo_mapping.json` stays as ingest's source for role and predicate names and for the ontology concepts, and `src/serka/ontology.py` keeps only what ingest needs.
- **Code changed or added**: `src/serka/pipelines.py`, `src/serka/graph/extractors.py` (now produces OKF concepts), a bundle writer, a bundle loader (chunks and relation records), the MCP `aggregate` tool, `scripts/ingest-data.py`, `mcp-server/src/serka-mcp/app.py` and `tools.py`, `src/serka/settings.py`, `src/serka/routers/query.py`, `src/serka/routers/dependencies.py`, `src/serka/routers/mock.py`, `src/serka/chat/pipeline.py`, `src/serka/chat/service.py`, `src/serka/prompts.py`, `src/serka/usage.py`.
- **UI**: `ui/src/api/search.ts`, `ui/src/stores/searchStore.ts`, `ui/src/pages/ResultsPage.tsx`, `ui/src/components/EntityResultCard.tsx`, `DatasetResultCard.tsx`, `RelationshipPanel.tsx`, `TypeChip.tsx`, `ui/src/typeMeta.tsx`, `ui/src/ontology.ts`, `ui/src/components/RunOverview.tsx`, `ui/src/run/runTrace.ts`.
- **Dependencies**: add `redis` and `redisvl`. Remove `neomodel`, `neo4j-haystack` and `sentence-transformers`/ONNX from the MCP server. Haystack stays for the ingest fetchers, splitter and Bedrock embedders.
- **Data**: the bundle lives in a local directory (default `./bundle`, git-ignored). Existing Neo4j data is not migrated; ingest is re-run.
- **Tests and docs**: `tests/test_writers.py`, `tests/test_mcp_server.py`, `tests/test_chat_pipeline.py`, `tests/test_app.py`, `tests/test_ontology.py`, `scripts/smoke-test.py`, `README.md`, `CONTRIBUTING.md`, `.env.example`.
- **Out of scope**: hosting or versioning the bundle outside the local machine, Redis LangCache itself, multi-hop graph search, aggregates that combine a text query with grouping by a related concept, JSON-LD output of any kind, zero-downtime reindexing, and moving the embedding cache (`.cache/embeddings`) into Redis.
