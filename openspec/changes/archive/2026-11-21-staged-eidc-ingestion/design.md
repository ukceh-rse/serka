# Design

## Context

`scripts/ingest-data.py` builds one Haystack pipeline (`PipelineBuilder.build_graph_pipeline`):

```
EIDCFetcher --> EntityExtractor --> ConceptHierarchyFetcher (GEMET, network) --+
     |                                                                          +--> OKFBundleWriter --> OKF_BUNDLE_DIR
     +--------> LegiloFetcher (hosted, LEGILO_PAT) --> DocumentTruncator -------+         (replaced)
```

then calls `load_from_settings`, which reads `OKF_BUNDLE_DIR`. HTTP goes through one `requests_cache` session with a 5 s default timeout. `build_concepts(records, nodes, relationships, documents)` in `okf/concepts.py` is the single place that turns these inputs into concepts; it reads each document's `meta.uri` and `meta.filename`.

The local Legilo (`supporting-docs-md` branch) is a FastAPI app. `GET /{id}/documents` converts every file under `SUPPORTING_DOCS_DIR/<id>/` with `anydoc` (`ocr="reject"`) and returns `{"success": {basename: markdown}, "errors": {basename: {"description": ...}}}`. It needs `DATA_DIR` and `SUPPORTING_DOCS_DIR` set to start, has no authentication, and pins `fastapi ~= 0.112` and `numpy ~= 1.26`. Serka locks `fastapi 0.136` and `numpy 2.4`, so the two cannot share an environment.

Original supporting files are published at `https://data-package.ceh.ac.uk/sd/<id>.zip`, with the documents under `supporting-documents/` inside the zip.

## Goals / Non-Goals

**Goals:**
- Reuse `EntityExtractor` and `build_concepts` unchanged, so bundle content changes only where the `okf-bundle` delta says.
- Building a bundle touches only the local filesystem and the local Legilo container.
- Each stage can be run and rerun on its own.

**Non-Goals:**
- Storing raw data or bundles anywhere other than local disk (object store, git).
- Parallel downloads or conversions. Sequential is enough for the first rollout; measure first.
- Running Legilo's other endpoints (variables, keywords) or its LLM features.
- Detecting datasets that were unpublished or changed after download, beyond `--refresh`.

## Decisions

### Raw store layout

```
raw/                                  (RAW_DIR, default ./raw)
  order.json                          {"seed": 20261120, "head": [...], "ids": [...]}
  metadata/<id>.json                  EIDC ?format=json, as returned
  supporting-docs/<id>/<path>         unzipped supporting-documents/ entries; mounted into Legilo
  status/<id>.json                    {"downloaded": iso8601, "has_supporting_docs": bool}
  markdown/<id>/<basename>.md         Legilo output
  markdown/<id>/_result.json          {"converted": iso8601, "errors": {basename: reason}}
  gemet/<sha1(uri)>.json              broader-concept response for one concept URI
```

- `status/<id>.json` is written last, after the metadata and the files are in place. Its presence is what marks a dataset as complete, which makes an interrupted download safe to resume. The zip is downloaded and extracted into a temporary sibling directory and renamed into place, as `write_bundle` already does.
- `supporting-docs/` contains only original files, because Legilo converts every file in a dataset's folder. Metadata and Markdown are kept elsewhere so Legilo never sees them.
- `markdown/<id>/_result.json` marks conversion as done for that dataset, including when every file failed. Builds skip datasets that have it, unless `--refresh` is given.
- Alternative: keep relying on the `requests_cache` folder as the raw store. Rejected because it can't be browsed, it holds Legilo's plain text rather than original files, and it can't be mounted into Legilo.

### Dataset order

The first download fetches every published dataset ID with one EIDC search (`rows` large enough for the whole catalogue, the same `state:published AND recordType:Dataset` term), then puts the ids-file IDs first and shuffles the rest with `random.Random(seed)` over the IDs sorted. Sorting before shuffling makes the order depend only on the set of IDs and the seed, not on EIDC's response order. The seed defaults to a fixed constant and can be overridden. `order.json` is created once. Later downloads load it and append newly published IDs, shuffled with the same seed, at the end, so existing prefixes never change. Changing the ids file or seed afterwards needs `--reorder`, which rewrites the order. Bundles built before that no longer match the new prefixes.

### Stages and scripts

```
scripts/download.py  [N|all] [--ids-file F] [--seed S] [--refresh] [--reorder]
scripts/build-bundle.py  N|all  [--out DIR]          default DIR: BUNDLES_DIR/<N|full>
scripts/load-bundle.py  [DIR]                        default DIR: OKF_BUNDLE_DIR
scripts/ingest-data.py  [N|all] [--ids-file F] [--no-load]   = download + build + load
```

- **Download** fetches metadata for the selected IDs, the `sd/<id>.zip` (a 404 counts as no supporting docs), and then the GEMET broader walk for every GEMET theme of the stored datasets. To find those themes it runs `EntityExtractor` over the stored metadata and gives `ConceptHierarchyFetcher` a raw-store-backed lookup.
- **Build** reads metadata for the first N IDs, runs `EntityExtractor`, runs `ConceptHierarchyFetcher` against the stored GEMET responses only (a missing response is a warning and an empty broader list, never a network call), converts any dataset that has no `_result.json` by calling local Legilo, then turns the cached Markdown into `Document`s (`meta.uri`, `meta.title`, `meta.filename`) and calls `build_concepts` / `write_bundle` with the output directory.
- `ConceptHierarchyFetcher` keeps its algorithm but takes its broader lookup as a parameter. Download passes "fetch and store"; build passes "read stored".
- `ingest-data.py` keeps its name and the `N` / `--ids-file` / `--no-load` interface, so `setup.sh` and `smoke-test.py` keep working with the least change.
- The Haystack pipeline is not kept for these stages. Each stage is a short sequence of plain function calls, and `PipelineBuilder` is removed along with the `LegiloFetcher` component. The components it wired (`EntityExtractor`, `ConceptHierarchyFetcher`) are called directly. Alternative: keep a pipeline per stage. Rejected because nothing branches or runs in parallel, and the pipeline only hid the data flow.

### Local Legilo service

```yaml
legilo:
  profiles: ["ingest"]
  build: { context: "${LEGILO_SRC:-../legilo}", dockerfile_inline: "<legilo's build steps, current uv>" }
  ports: ["${LEGILO_PORT:-8100}:8000"]
  environment: { SUPPORTING_DOCS_DIR: /docs, DATA_DIR: /tmp }
  volumes: ["${RAW_DIR:-./raw}/supporting-docs:/docs:ro"]
```

- Legilo's own Dockerfile pins uv 0.4.2, which cannot parse the `supporting-docs-md` branch's `uv.lock`, so the service builds from an inline copy of Legilo's build steps with a current uv. Drop it once Legilo's Dockerfile is fixed. `LEGILO_SRC` defaults to `../legilo` rather than being required, because a required variable would make every compose command fail without it.
- The `ingest` profile means `docker compose up` for the app doesn't build Legilo. You start it with `docker compose --profile ingest up -d legilo`. The host port is 8100 because `mcp` already publishes 8000.
- Serka calls `LEGILO_URL` (default `http://localhost:8100`) with a plain `requests` session: no auth header, no cache, and a long per-request timeout (`LEGILO_TIMEOUT`, default 600 s), because anydoc on a large PDF takes far longer than 5 s.
- Before a build converts anything, it checks that Legilo answers. If not, it stops with an error naming `LEGILO_URL`, which keeps the raw store and the existing bundle unchanged.
- Legilo keys results by basename. The build compares the returned names with the stored files, and a basename that appears twice under one dataset gets a warning (the spec's duplicate scenario). Only one of the two files can be returned, which is accepted as Legilo's behavior.
- A file Legilo reports under `errors` goes into `_result.json` with its reason. A dataset-level failure (HTTP error, timeout) is logged and leaves no `_result.json`, so the next build tries again.
- Alternatives: importing Legilo as a library (dependency conflict above), or a one-shot script run in Legilo's own environment (needs a new Legilo script and couples Serka to the checkout path at runtime). The user chose the service.

### Settings

- Add `raw_dir` (`./raw`), `bundles_dir` (`./bundles`), `legilo_url` (`http://localhost:8100`) and `legilo_timeout` (600).
- Remove `legilo_pat`.
- `okf_bundle_dir` stays as the default for `load-bundle.py` with no argument and for the smoke test.
- `.gitignore` gains `/raw/` and `/bundles/`.

### Removed processing

`DocumentTruncator` and `LegiloFetcher._is_prose` are removed. The loader already splits each concept into chunks before embedding, so truncation only threw text away, and anydoc output is Markdown rather than raw extracted text, so the whitespace check no longer measures anything useful. `CachedDocumentEmbedder` already caps each chunk's length (`max_chars`), so a very long document can't overflow an embedding request.

## Risks / Trade-offs

- [Legilo's `supporting-docs-md` branch is not pushed to `NERC-CEH/legilo`, so a deploy host cannot build it] → `setup.sh` clones Legilo at `LEGILO_REF` from GitHub and fails clearly if the clone fails. Pushing the branch (or merging it) is a prerequisite for deploying this change.
- [The full collection's original files may need a lot of disk] → record raw store size at 20 and 100 and extrapolate before the full download; `raw/` can live on another disk through `RAW_DIR`.
- [Embedding the full bundle with Bedrock costs money and time] → record chunk count and load time at 20 and 100 and estimate the full load before running it.
- [anydoc on large or odd files can take minutes or hang] → a per-request timeout; a timed-out dataset has no `_result.json` and is retried on the next build; record the slowest datasets during rollout.
- [EIDC search may cap `rows`] → the ID listing pages until it has `numFound` IDs and fails if the count disagrees.
- [The data-package zip may contain no `supporting-documents/` folder or unexpected layouts] → treat it as no supporting docs and log a warning; the smoke datasets all have documents and cover the normal path.
- [Basename collisions lose one file's Markdown] → logged per dataset; fixing it needs a change in Legilo.

## Migration Plan

1. Archive `replace-neo4j-with-redis-okf` first, so `okf-bundle` exists in `openspec/specs/`.
2. Developers check out Legilo `supporting-docs-md`, set `LEGILO_SRC`, and start `docker compose --profile ingest up -d legilo`. `LEGILO_PAT` can be removed from `.env`.
3. Run the rollout: 20, then 100, then the full collection, each built into its own directory and loaded in turn.
4. Rollback is a git revert. The old `./bundle` directory is still loadable with `load-bundle.py ./bundle`.

## Open Questions

- Should the deploy host build its own bundle at all, or download a bundle built elsewhere? `setup.sh` already notes that data "should be imported and processed separately". This change keeps `ingest-data.py 100` working there, and shipping pre-built bundles can follow later.
