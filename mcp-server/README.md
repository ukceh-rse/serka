# Serka MCP server

Serves the EIDC catalogue to agents over MCP, from the Redis indexes (`idx:chunks` and `idx:relations`) that `scripts/load-bundle.py` builds from the OKF bundle.

## Tools

- `search(query?, sort_by?, order="descending", type?, theme?, linked?, bounding_box?, published_after?, published_before?, min_citations?, limit=25)` returns `{hits, total, warnings}`. Each hit is `{chunk_id, text, score, concept: {id, type, title, description, resource, tags, citations?, published?}}`, a passage of a concept file with its concept's summary.
  - With a query only, chunks are ranked by Redis `FT.HYBRID`: full-text (BM25) and vector similarity merged by reciprocal rank fusion. One hit per chunk, and `total` counts matching chunks.
  - With `sort_by` (`citations` or `published`) and no query, every concept matching the filters is sorted exactly, one hit per concept, and `total` counts concepts.
  - With both, the most relevant concepts for the query (a window of at least 50) are sorted. This is approximate.
  - Theme, bounding box, date and citation filters match only datasets and their supporting documents.
- `read(id)` returns a whole concept file (frontmatter and markdown body) by concept ID, such as `datasets/<eidc-id>` or `/people/<orcid>`, or an index such as `ontology/index`.
- `aggregate(group_by?, role?, sort_by="datasets", query?, type?, theme?, linked?, bounding_box?, published_after?, published_before?, min_citations?, limit=10)` counts exactly over the whole catalogue, for questions such as "how many datasets are there?" or "which author contributed to the most datasets?". It returns `{total, citations?, groups?, total_groups?, warnings}`.
  - With no `group_by`, `total` is the number of datasets (or concepts of `type`) matching the filters, and `citations` their summed citation counts. A `query` counts the datasets that mention any of its words in their own text or a supporting document (full-text, not semantic), each once.
  - `group_by` `person` or `organisation` (optionally narrowed by `role`, such as `author`), `grant`, `funder` or `theme` returns `{id, title, datasets, citations}` groups: the number of distinct matching datasets each is related to and their summed citations, ordered by `sort_by`. A theme counts the datasets of its narrower themes. These groups come from the `idx:relations` index, which has one record per dataset and related concept, because Redis groups a document under only one value of a multi-value field. A `query` cannot be combined with these groups.
  - `group_by` `year` counts datasets per publication year, and `type` counts concepts per type.
- `geocode_location(location)` returns a bounding box for a UK place name (Nominatim).

Results are plain JSON, not JSON-LD.

## Environment

- `REDIS_URL`: the Redis holding the index (default `redis://localhost:6379`).
- `MODELS_EMBEDDING`: the Bedrock embedding model used for queries (default `amazon.titan-embed-text-v2:0`). It must match the model the bundle was loaded with.
- AWS credentials and region for Bedrock, from the usual AWS chain (for example `AWS_PROFILE` and `AWS_DEFAULT_REGION`).

The server reads a `.env` file in the working directory.

## Run

Start the MCP server from the repository root using:
```
uv run mcp-server/src/serka-mcp/main.py
```
It listens on port 8000 at `/mcp/`. You can then check it is working correctly using:
```
npx @modelcontextprotocol/inspector
```
