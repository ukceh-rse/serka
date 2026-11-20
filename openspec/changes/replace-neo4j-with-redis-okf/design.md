# Design

## Context

See proposal.md for motivation and the specs for required behaviour.

- **Data flow today.** `scripts/ingest-data.py` runs a Haystack pipeline. `EIDCFetcher` and `LegiloFetcher` fetch records and supporting files. `EntityExtractor` and `ConceptHierarchyFetcher` turn them into typed nodes and relations. A splitter and Bedrock embedders prepare text chunks, and `Neo4jGraphWriter` MERGEs everything into Neo4j.
- **Who touches Neo4j.** Only the MCP server reads it (`queries.py`, through `tools.py`). The serka API and the chat pipeline reach the catalogue through MCP tools alone (`routers/dependencies.py`: `fastmcp.Client` for `/query`, `MCPToolset` for insight retrieval). Swapping the store therefore means changing ingest and the MCP server. The tool surface change then spreads to prompts, tests, the mock router and the UI.
- **Where JSON-LD is used.** Every tool result and `/v1/query/semantic` return JSON-LD with DOO CURIEs. The UI's `searchStore.ts`, `EntityResultCard.tsx`, `RelationshipPanel.tsx`, `typeMeta.tsx` and `ontology.ts` read `@graph`, `@type` and the search `path`/`via`.
- **Vocabulary.** `src/serka/doo_mapping.json` already holds DOO prefixes, node types, roles, role classes, predicates and plain-language `definitions`. That is enough to generate the ontology concepts without parsing the DOO TTL.
- **Redis.** Redis Open Source 8.10.3 is the newest official image. `FT.HYBRID` (8.4 and later) runs a `SEARCH` text clause and a `VSIM` vector clause and merges them with `COMBINE RRF` (defaults: window 20, constant 60) or `LINEAR`. It merges scores only; it is not a model reranker. In 8.4.0, a `FILTER` after `COMBINE` was unsupported, so filters must go into both clauses.
- **LangCache.** It is offered only on Redis Cloud, or self-managed on Kubernetes under a private-preview licence. RedisVL's `SemanticCache` and `LangCacheSemanticCache` share one check/store interface.

## Goals / Non-Goals

**Goals:**
- Search covers every concept file through one index and one query shape.
- The index can be rebuilt quickly and repeatably from the bundle, re-using cached embeddings.
- Swapping the answer cache to LangCache later is a change to one small module.

**Non-Goals:**
- Serving reads while a reload is in progress. Loading drops and rebuilds the index, so search is briefly empty or partial while it runs.
- Incremental ingest. Each run rebuilds the bundle from scratch (see the decision below).
- Making the bundle validate under Google's reference OKF parser beyond the v0.2 conformance rules.
- Evaluating ranking quality against the old cross-encoder beyond the existing smoke test datasets.

## Decisions

### The bundle is the source of truth and Redis is derived from it

Ingest and loading are separate steps:

```
 ingest-data.py                         load-bundle.py
 EIDC + Legilo                          bundle/  --parse--> concepts
   -> extract -> OKF writer -> bundle/           --chunk--> chunks
                                                 --embed--> (cached by content hash)
                                                 --write--> Redis: drop + rebuild chunk and relation indexes
                                                 --clear--> answer cache
```

By default `ingest-data.py` runs the load after writing the bundle (`--no-load` skips it). `load-bundle.py` on its own rebuilds Redis from an existing bundle, with no access to EIDC or Legilo.

The OKF writer builds the bundle in a temporary sibling directory and renames it over the configured directory (`OKF_BUNDLE_DIR`, default `./bundle`, git-ignored) when it finishes. A failed run therefore never leaves a half-written bundle.

**Replacing over merging:** today's MERGE keeps adding to the graph, so `--ids-file` subsets accumulate. Replacing the bundle removes stale concepts without tracking them, but an ingest of a subset now *replaces* the catalogue with that subset. This is a deliberate default. Re-ingest is cheap because embeddings are cached. Incremental ingest can come with the later work on bundle storage.

*Alternatives:* Redis as the source of truth with the bundle exported from it (loses diffable files, and agents can't read the bundle directly). Writing straight into Redis during ingest (couples ingest to Redis, and nothing could be rebuilt without re-fetching).

### Concept layout and IDs

```
 bundle/
   index.md                       okf_version: "0.2", links to each directory
   datasets/index.md
   datasets/<eidc-id>.md          type: dataset
   datasets/<eidc-id>/docs/<source-id>.md   type: document
   people/<id>.md                 type: person
   organisations/<id>.md          type: organisation  (funders tagged "funder")
   grants/<id>.md                 type: grant
   themes/<id>.md                 type: theme
   ontology/index.md
   ontology/types/<name>.md       type: ontology
   ontology/roles/<name>.md       type: ontology
   ontology/predicates/<name>.md  type: ontology
```

- **IDs.** The EIDC ID for datasets. The ORCID or ROR identifier for people and organisations when present. Otherwise the first 12 hex characters of the SHA-256 of the source URI, which keeps IDs stable without leaking names into paths. A document's ID is the splitter's `source_id`, as today, so files with the same name stay distinct.
- **Funders.** They are `organisation` concepts tagged `funder`, which matches today's `Organisation:FundingAgency` double label.
- **Citations.** Citing papers (today's `Document` nodes) become a "Cited by" list of links to their external URLs in the dataset body, not concepts. They have no local content worth chunking.
- **Dataset frontmatter extension keys:** `published` (ISO date), `citations` (int), `bbox` (`{north, south, east, west}`), `themes` (theme concept IDs, ancestors included), `contributors` (`[{id, roles}]`, with role names as `ontology/roles/` file names, such as `author` and `contact-person`), `grants` (grant concept IDs) and `funders` (organisation concept IDs of the grants' funders), plus `licence`, `access_rights`, `temporal` and `identifiers` passed through. `themes`, `contributors`, `grants` and `funders` repeat what the body says, in a form the loader reads without parsing prose (see "Aggregate questions").
- **Body.** The description, then the lineage, under headings. Then a "Contributors" list in the form ``[Jane Smith](/people/0000-0002-...) — [author](/ontology/roles/author)``, then "Related", "Funding", "Supporting documents" and "Cited by" sections.

The OKF writer replaces `Neo4jGraphWriter` as the sink of the existing pipeline, and consumes the `EntityExtractor` and `ConceptHierarchyFetcher` outputs unchanged. `BedrockNodeEmbedder` and the document embedding step leave the ingest pipeline and move to loading. `TextExtractor` is no longer needed, because description and lineage go into the dataset body.

### Ontology concepts come from the DOO mapping

One concept is generated for each node type, role and predicate that the run's bundle actually uses. The title is the term's local name, `description` comes from `definitions`, and `resource` is the full DOO/IRI. The body names the CURIE and, for roles, the role class (for example "a kind of publishing role"). This keeps `src/serka/doo_mapping.json` as ingest-time vocabulary only. The MCP and UI copies and `scripts/sync-doo-mapping.py` are deleted.

*Alternative:* parse `doo-0.3.3.ttl` with rdflib. That gives richer definitions, but adds a runtime dependency, and the mapping already covers every term ingest emits.

### Redis data model

```
 concept:<id>          STRING  raw markdown file (what read() returns)
 chunk:<id>#<n>        JSON    {
                                 concept, type, title, description, resource,
                                 tags[], text,
                                 dataset,                  # the dataset's ID, on its own and its documents' chunks
                                 lead,                     # 1 on a concept's first chunk, else 0
                                 links[],                  # concept IDs this concept links to
                                 themes[], published, citations,
                                 north, south, east, west, # dataset fields, also on its documents
                                 embedding[1024]
                               }
 idx:chunks            FT index ON JSON PREFIX chunk:
                         text TEXT, title TEXT WEIGHT 2
                         concept TAG, type TAG, tags TAG, links TAG, themes TAG, dataset TAG
                         lead NUMERIC
                         published NUMERIC SORTABLE, citations NUMERIC SORTABLE
                         north/south/east/west NUMERIC
                         embedding VECTOR HNSW FLOAT32 DIM 1024 COSINE
 rel:<dataset-id>#<n>  JSON    {
                                 dataset, kind,            # kind: person | organisation | grant | funder | theme
                                 target, target_title,     # the related concept
                                 roles[],                  # contributor roles; empty for other kinds
                                 themes[], links[], published, citations,
                                 north, south, east, west  # the dataset's filter fields
                               }
 idx:relations         FT index ON JSON PREFIX rel:
                         dataset TAG, kind TAG, target TAG SORTABLE, target_title TAG SORTABLE
                         roles TAG, themes TAG, links TAG
                         published NUMERIC, citations NUMERIC
                         north/south/east/west NUMERIC
 theme-label:<lower>   STRING  theme concept ID, for theme filters given by label
```

- **Concept fields copied onto every chunk.** This lets one query filter and return a concept summary without a second lookup. `links` is the whole concept's set of outgoing links, so a linked-concept filter matches every chunk of a concept that links the target.
- **Dataset fields on document chunks.** A document's chunks carry its dataset's filter fields, so a bounding box search can surface a matching methods PDF. Chunks of people, organisations, grants, themes and ontology concepts have no dataset fields, so dataset-only filters exclude them without special handling.
- **Bounding boxes** stay as four NUMERIC fields with today's overlap test and roughly 20% expansion (`BoundingBox.expand(20)`). GEOSHAPE would need polygon WKT for no gain on rectangles.
- **Dates** are stored as days since the epoch.

The vector dimension comes from the embedding model in settings (Titan v2: 1024), so changing models means a reload, not a code change.

### Chunking

The body of each concept is split by Haystack's `DocumentSplitter` (word, 150/50, as today). The text that gets embedded is `"<title>\n\n<chunk>"`, so short chunks keep their subject. The stored `text` is the chunk alone. A concept with an empty body gets a single chunk of title plus description.

`CachedDocumentEmbedder` and its content-hash file cache are reused as they are, so reloading an unchanged bundle makes no Bedrock calls. Moving that cache into Redis is out of scope.

### Hybrid search query

```
 FT.HYBRID idx:chunks
   SEARCH "(@text|title:<escaped terms>) <filters>"
   VSIM @embedding $vec KNN 2 K <window> FILTER "<filters>"
   COMBINE RRF 2 WINDOW <window>
   LOAD * ... LIMIT 0 <limit>
   PARAMS 2 vec <blob>
```

- `window = max(20, 2 * limit)`, so a larger `limit` still has candidates from both sides.
- The same filter expression goes into the `SEARCH` clause and the `VSIM FILTER`. A query with only stopwords or punctuation falls back to a match-all text clause plus the filters, so the vector side still runs.
- **Client.** The first implementation task is a spike to confirm whether the locked `redisvl` exposes `HybridQuery` for `FT.HYBRID`. If not, the next choice is redis-py's hybrid search API, and the last resort is `execute_command` with the reply parsed in one function. The rest of the code depends only on a `hybrid_search(query, embedding, filters, limit) -> list[Hit]` function.
- **Spike result (task 1.4, redis 8.1.0, redisvl 0.31.0, Redis 8.10.3).** redis-py's `ft().hybrid_search` (with `HybridQuery`, `CombineResultsMethod` and `HybridPostProcessingConfig`) is used. It handles every mode: RRF with `WINDOW`, the filter in both `SEARCH` and `VSIM FILTER`, `LOAD`, `LIMIT`, and `SORTBY` after `COMBINE`, and it reports `total_results`. RedisVL's `HybridQuery` was rejected: it ties KNN `K` to `num_results`, takes one text field, raises on stopword-only text and has no `SORTBY`. `execute_command` also works for every mode and remains the fallback. Other findings: `* <filters>` is a syntax error, so the match-all text clause is the filter expression alone (or `*` with no filters). A bare `*` text clause would let unfiltered chunks in through the text side. `@__key` and `@__score` (the fused score) can be loaded, but loading a `YIELD_SCORE_AS` alias fails with `SEARCH_FIELD_DUP`. Query syntax errors raise `ResponseError` starting `SEARCH_SYNTAX`.
- **Warnings.** The MCP tool keeps today's `warnings` mechanism for dataset-only filters used with a non-dataset type, and for full-text syntax errors (retried as vector-only).

### Sorted search for ranking questions

Questions like "most cited dataset" or "newest datasets near Windermere" have no terms to rank by relevance, and the agent cannot answer them by reading every dataset. `search` has three modes:

```
 query, no sort_by      FT.HYBRID ... (above)                      one hit per chunk
 sort_by, no query      FT.SEARCH idx:chunks "@lead:[1 1] <filters>"
                          SORTBY <field> <order> LIMIT 0 <limit>   one hit per concept, exact
 query + sort_by        FT.HYBRID ... FILTER "@lead:[1 1]"         one hit per concept,
                          window = max(50, 5 * limit), then          sorted within the
                          SORTBY <field> <order>                     relevant window
```

- **The `lead` marker.** Filtering on `lead` gives one hit per concept without `GROUPBY`, and the lead chunk carries the full concept summary. In the query-plus-sort mode, `lead` restricts the vector and text sides to lead chunks. A concept that matches only deep in a supporting document can then be missed. That is acceptable for "most cited X", where X is usually a topic in the title or description.
- **The window.** Query-plus-sort is approximate by nature: it ranks only the relevant window. The tool description and the insight prompt say so, and tell the agent to prefer a `theme` filter with no query when X is a catalogue theme, since that sort is exact.
- **Sort fields.** `sort_by` is limited to `citations` and `published`, the fields `list_datasets` sorts on today. These are dataset fields, so a sorted search of non-dataset types returns them unordered at the end. The tool warns when `sort_by` is used with a type other than `dataset` or `document`.
- **Totals.** Every mode reports `total` from the reply's `total_results`. For a sorted search, `total` counts concepts, and for an unsorted one it counts chunks (or fused candidates). The tool description states which, and sends counting questions to `aggregate`.

**Keyword path.** The keyword planner's output gains `sort_by` and `order` alongside the existing terms and filters, and `terms` becomes optional. The plan-keyword prompt gets examples ("most cited datasets", "latest datasets on X"). The single direct `search` call passes them through.

*Alternative:* generated ranking concepts in the bundle (for example `datasets/most-cited.md`). They are exact and cheap to read, but cover only questions decided in advance and cannot combine with filters.

*Alternative:* `FT.SEARCH` and `FT.SEARCH KNN` with RRF in Python, as today. That means two round trips and our own merge code. Native `FT.HYBRID` is what was asked for.

### Aggregate questions

Typical high-level questions need exact numbers over the whole catalogue, not ranked passages: "how many datasets are there?", "which author contributed to the most datasets?", "which funder funds the most freshwater datasets?", "who is the most cited author?", "how many datasets were published each year?", "how many datasets mention ozone?". The agent cannot answer these by reading search results, so a fourth tool answers each in one call:

```
 aggregate(group_by?, role?, sort_by="datasets", query?, type="dataset",
           theme?, linked?, bounding_box?, published_after?, published_before?,
           min_citations?, limit=10)
   -> {total, citations?, groups: [{id, title, datasets, citations}], total_groups, warnings}

 no group_by        FT.AGGREGATE idx:chunks "@lead:[1 1] @type:{<type>} <filters>"
                      GROUPBY 0 REDUCE COUNT 0, SUM @citations
                    with query: "@text|title:(<terms>) <filters>"
                      GROUPBY 0 REDUCE COUNT_DISTINCT @dataset (or @concept for non-datasets)
 group_by=year      FT.AGGREGATE idx:chunks "@lead:[1 1] @type:{dataset} <filters>"
                      APPLY year(@published * 86400) AS year GROUPBY @year, sorted by year
 group_by=type      FT.AGGREGATE idx:chunks "@lead:[1 1]" GROUPBY @type   (catalogue overview)
 group_by=person | organisation | grant | funder | theme
                    FT.AGGREGATE idx:relations "@kind:{<kind>} @roles:{<role>} <filters>"
                      GROUPBY @target REDUCE COUNT 0 AS datasets, SUM @citations,
                      FIRST_VALUE @target_title; SORTBY <sort_by> DESC, title; LIMIT <limit>
                    total_groups from a second GROUPBY 0 REDUCE COUNT_DISTINCT @target
```

- **Why a second index.** A spike on Redis 8.10.3 against the 100-dataset test bundle (2026-11-10) showed that `GROUPBY` on a multi-value TAG (`links`, `themes`) puts each document in one group only. Grouping dataset lead chunks by `@links` gave the EIDC custodian organisation 13 datasets, where a `@links` filter counts 100, and the top person 9 instead of 20. Any grouping over a many-to-many relation therefore needs one single-valued record per pair. `GROUPBY` on single-valued fields (`year`, `type`), `COUNT_DISTINCT` and `SUM` gave exact results in the same spike.
- **Relation records.** The loader writes one `rel:` record per (dataset, related concept) pair, for each contributor, grant, funder and theme, with no embedding. With one record per pair, `COUNT` is the number of distinct datasets even when a person has two roles on one dataset: `roles` holds both, and a `role` filter matches either. The dataset's filter fields are copied onto the record, as onto chunks, so `aggregate` reuses `search`'s filter-expression builder unchanged. At EIDC scale this is a few records per dataset (about 15 on the test bundle), small next to the chunks.
- **Where relations come from.** From the dataset frontmatter keys `contributors`, `grants`, `funders` and `themes`, not from the body. The body's contributor, funding and related lines differ in shape (roles after the link, the predicate in a section intro, a funder trailing a grant), so parsing them back would tie the loader to the writer's prose. `themes` already sets the precedent of frontmatter that repeats the body.
- **Kinds and roles.** `person` and `organisation` group contributors, and `role` (an `ontology/roles/` name) narrows them. `funder` groups the funders of a dataset's grants, and `grant` groups the grants. `theme` groups by theme with ancestors included, so a broad theme counts the datasets of its narrower themes. The tool description says so. An unknown `role` is a tool error that lists the roles in use.
- **Text queries count matches, not similarity.** `query` is full-text only: vector similarity has no cut-off, so "how many datasets are about X" has no exact answer, while "how many mention X" does. Matches are counted as distinct `dataset` values, the new chunk field, so a term found only in a methods PDF counts its dataset once. `query` with a relation `group_by` returns no groups and a warning pointing to `theme`. Supporting it means matching datasets first and then filtering relations by thousands of IDs, which can come later if needed.
- **Ranking.** `sort_by` is `datasets` (default) or `citations`, the summed citation counts of a group's datasets ("most cited author"). Ties are broken by title, so results are stable.
- **Warnings.** The dataset-only filter rules from `search` apply. `role` without a `person` or `organisation` group, and `type` other than `dataset` with a relation group, are reported as warnings.
- **Agent route.** Aggregate questions are classified as `insight`, with examples in the classifier prompt, and the insight plan prompt names `aggregate` for counts and rankings. The keyword path stays a single search that lists matches. The answer prompt's rule against stating counts becomes: state counts only as returned by `aggregate`, say what was counted (for example "datasets with this person as author"), and never estimate.

*Alternative:* precomputed counts on concepts (for example `datasets: 20` on a person, sortable on chunks). Exact, and it reuses sorted search, but it cannot combine with filters ("top authors of freshwater datasets since 2015"), and each new question needs a new field.

*Alternative:* a generated `statistics.md` concept in the bundle. Readable by any agent, but it answers only questions decided in advance.

*Alternative:* client-side counting by paging through `FT.SEARCH` results in the MCP server. Correct, but it moves every dataset's links over the wire for each question, and the Redis-side grouping is what the index is for.

### MCP tools and result shape

`search(query?, sort_by?, order="descending", type?, theme?, linked?, bounding_box?, published_after?, published_before?, min_citations?, limit=25)` returns `{hits: [...], total, warnings: [...]}`. Each hit is `{chunk_id, text, score, concept: {id, type, title, description, resource, tags, citations?, published?}}`. For sorted hits, `score` is the sort value's rank position. `read(id)` returns the markdown string. `aggregate` is described under "Aggregate questions". `geocode_location` is unchanged. The app drops `neo4j_driver`, `CrossEncoder` and `reranking_enabled`, and gains one Redis client.

Theme resolution: a value containing `/` is treated as a theme concept ID. Otherwise `theme-label:<lowercased>` is looked up, and an unknown theme is a tool error, as today. The `themes` TAG already holds the ancestors, so no expansion happens at query time.

Prompts list the four tools, send counting and ranking questions to `aggregate`, explain that results are passages and that `read` follows `/...` links, and point the agent at `read("ontology/index")` for role and predicate meanings. `render_tool_results` in the chat pipeline stops unwrapping JSON-LD and renders hits as `concept title (resource): text` and aggregate groups as `title (id): N datasets, M citations` under a line naming what was counted.

### Plain search endpoint

`/v1/query/semantic` passes the MCP `search` hits through unchanged as a list (warnings are dropped, as today's `@graph`-only response does). `return_type` and `hops` are replaced by `type` (a free string, not an enum), so new OKF types need no API change.

### Results page grouping

`searchStore` keeps the hit list from the API and derives groups: it buckets hits by `concept.id`, orders the groups by their best score, and orders hits within a group by score. A new `ConceptResultCard` replaces `EntityResultCard` and `DatasetResultCard`. `RelationshipPanel` is removed, because hits no longer have paths. `typeMeta.tsx` maps OKF types to label and icon, with a generic fallback. A document's dataset ID is derived from its concept ID (`datasets/<id>/docs/...` → `datasets/<id>`), so linking to it needs no extra request.

### Answer cache

A module `serka/answer_cache.py` wraps RedisVL `SemanticCache` behind `lookup(query) -> CachedAnswer | None`, `store(query, CachedAnswer)` and `clear()`. `CachedAnswer` is `{text, path, score, model}`, kept in the entry's metadata. Its vectorizer is RedisVL's Bedrock text vectorizer with the configured embedding model (or a thin wrapper around the existing Haystack embedder, if the RedisVL one cannot use the same AWS credentials chain). Settings: `ANSWER_CACHE_DISTANCE_THRESHOLD` (default 0.05 cosine distance, strict), `ANSWER_CACHE_TTL_SECONDS` (default 7 days), and `ANSWER_CACHE_ENABLED` (default on, forced off in test mode).

Moving to LangCache later means swapping `SemanticCache` for `LangCacheSemanticCache` inside this module.

**Flow and the usage limiter:**

```
 route: check caps (no count) --over--> 429
          | under
          v
 stream: first turn? --no--------------------------+
          | yes                                    |
          v                                        v
        [cache step] lookup --hit--> emit cached   count run (admit)
          | miss                    answer +       classify -> ... -> outcome
          +------------------------ outcome        |
                                    `cached`       +-- accepted & first turn -> store
```

The limiter gains a check-only call. The existing admission count moves to after a cache miss, inside the stream's start. Daily caps are rejected before any stream starts, as before.

*Alternatives:* look the cache up before the cap check (over-cap clients would get answers, which the spec rules out), or count cache hits (simpler, but it charges users for answers that cost nothing).

**Why the cache step runs before `classify`:** a hit skips every chat model, including classification. Only accepted answers are stored, so a cached query was already in scope when it was answered. A refusal-worthy prompt can only hit by being within the strict threshold of an accepted in-scope one.

### Services and configuration

- `compose.yaml`: replace `neo4j` with `redis:8.10.3`, with a named volume and default RDB persistence. Redis is a rebuildable index, so AOF is not worth its cost. `serka` and `mcp` depend on it and get `REDIS_URL=redis://redis:6379`.
- `terraform/scripts/setup.sh`: replace the Neo4j env and data directories with `REDIS_URL` and a Redis data directory. Terraform resources change only where they name Neo4j.
- `settings.py`: remove `neo4j_*`, add `redis_url`, `okf_bundle_dir` and the `answer_cache_*` settings. The MCP server reads `REDIS_URL` from its environment, as it reads `NEO4J_*` today.

## Risks / Trade-offs

- [Rank fusion without the cross-encoder ranks worse for single-shot callers (`/query`, the keyword path)] → Agents compensate with repeated searches. `title` gets weight 2 for BM25. Run the smoke-test datasets before and after, and tune `WINDOW`/`CONSTANT` or switch to `LINEAR` if needed. The fusion parameters stay in one function.
- [A semantic cache returns an answer to a subtly different question, such as "pike in Windermere" vs "perch in Windermere"] → A strict default threshold, first turns only, accepted answers only, and a clear on every reload. The cached outcome is visible in the summary row, so users can see it was not freshly composed.
- [A subset ingest replaces the whole catalogue] → Document it in the ingest script's help and in the README. Incremental ingest belongs with bundle storage work.
- [The cache lookup and the cap check are not atomic, so concurrent first-turn misses from one client can overshoot its cap by the number in flight] → Accepted: the overshoot is bounded by concurrency in one process, and every overshooting run is still counted.
- [FT.HYBRID client support may lag the server] → The spike task runs first, and a raw-command fallback is planned.
- [Copying concept and dataset fields onto every chunk multiplies storage] → Small at EIDC scale (thousands of datasets). Revisit if supporting documents grow large.
- [Relation records repeat what the body says, so the two can drift] → Both come from the same extractor output in one writer pass, and a writer test checks that every frontmatter relation is also linked in the body.
- [`aggregate` cannot combine a text query with grouping by a related concept] → It warns and points to `theme`. Matching datasets first and filtering relations by their IDs is a later addition if agents need it.
- [Search is empty during a reload] → Accepted for a local deployment (non-goal above). A later change can build a new index and switch to it with `FT.ALIASUPDATE`.
- [Concept IDs derived from hashes are not human-readable] → Titles are in the frontmatter and in index files. ORCID and ROR IDs are used where available.

## Migration Plan

1. Bring up Redis alongside Neo4j. Run ingest to write the bundle and load it.
2. Switch MCP, the API and the UI to the new tools and response shapes. Remove Neo4j from compose, settings, terraform and dependencies.
3. Run the smoke test against the new stack.

Rollback: check out the previous commit and re-ingest into Neo4j. No Neo4j data is migrated or deleted by this change, but the existing `.neo4j/` data directory is no longer used.

## Open Questions

- Exact RRF `WINDOW` and `CONSTANT` values, and the cache distance threshold. They are tuned against the smoke-test queries, and the defaults above apply until then.
  - *Comparison (task 11.2, 2026-11-10).* The 8 smoke-test queries were run through `/v1/query/semantic` on the 10 smoke-test datasets, against `origin/main` (`bb7fd73`: Neo4j vector and full-text search, RRF in Python, ONNX cross-encoder rerank, `return_type=Dataset`) and against this change (`FT.HYBRID` RRF, `type=dataset`, hits grouped by concept). Both ingests ran without Legilo supporting documents, as no `LEGILO_PAT` was available. The expected dataset ranked **1st on both stacks for all 8 queries**. Ranks 2 and below differ, but in a 10-dataset catalogue they are all unrelated datasets on both stacks, so the order carries no signal. The 25 hits now cover 8 to 10 distinct datasets instead of 10, because several chunks of the top dataset take hit slots. The Results page groups them, and agents can raise `limit`.
  - *Decision.* RRF stays at `WINDOW = max(20, 2 * limit)` and `CONSTANT 60`. The cache threshold stays at 0.05: the smoke test confirms an identical repeat is served from the cache and that the other questions miss, but a 10-dataset catalogue cannot tune paraphrase matching. Revisit both on a full ingest with supporting documents, where many datasets share topics.
- Whether `log.md` is worth writing per ingest run (OKF allows it, and nothing reads it yet).
