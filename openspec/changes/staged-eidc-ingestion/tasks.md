# Tasks

## 1. Prerequisites and settings

- [ ] 1.1 Confirm `replace-neo4j-with-redis-okf` is archived, and verify `openspec list --specs` shows `okf-bundle` and `openspec validate staged-eidc-ingestion` passes
- [ ] 1.2 Add `raw_dir` (`./raw`), `bundles_dir` (`./bundles`), `legilo_url` (`http://localhost:8100`) and `legilo_timeout` (600) to `src/serka/settings.py` and `.env.example`, remove `legilo_pat` from both, add `/raw/` and `/bundles/` to `.gitignore`, and verify `tests/test_settings.py` covers the new defaults and the removal

## 2. Raw store and dataset order

- [ ] 2.1 Add a raw store module (`src/serka/raw.py`) for the design's layout: paths per dataset, `is_complete(id)` from `status/<id>.json`, and atomic writing of a dataset's metadata and supporting files (temporary sibling and rename). Verify unit tests show a dataset without a status file is incomplete and a failed write leaves no partial dataset
- [ ] 2.2 Implement the dataset order in `order.json`: ids-file IDs first in file order with duplicates removed, the rest sorted and then shuffled with the seed, reuse on later runs with new IDs appended at the end, and `--reorder` to rebuild. Verify unit tests for nested prefixes, ids file first, the same order from the same inputs regardless of input order, and appended IDs
- [ ] 2.3 Implement listing every published EIDC dataset ID, paging until `numFound` is reached and failing if the count disagrees, and verify a unit test with a mocked two-page response

## 3. Download stage

- [ ] 3.1 Implement downloading one dataset: EIDC metadata JSON, `https://data-package.ceh.ac.uk/sd/<id>.zip` with only the `supporting-documents/` entries extracted (a 404 or no such folder counts as no supporting docs), then `status/<id>.json`. Verify unit tests with a mocked zip covering normal, 404 and folder-missing cases, and that a stored PDF matches the zip byte for byte
- [ ] 3.2 Make `ConceptHierarchyFetcher` take its broader lookup as a parameter and add raw-store lookups in two forms, "fetch and store under `gemet/`" and "read stored only, warn on missing". Verify unit tests show the stored-only form makes no HTTP request and gives the same hierarchy as the fetching form
- [ ] 3.3 Add `scripts/download.py [N|all] [--ids-file F] [--seed S] [--refresh] [--reorder]`. It creates or loads the order, skips complete datasets unless `--refresh` is given, logs and continues past a failed dataset, then fetches GEMET for the stored datasets' themes. Verify `uv run scripts/download.py 20` and then `100` fetch only the 80 new datasets (from its log), and a rerun after Ctrl-C resumes

## 4. Local Legilo conversion

- [ ] 4.1 Add the `legilo` service to `compose.yaml` under the `ingest` profile, as in the design (build from `LEGILO_SRC`, port `LEGILO_PORT:-8100`, `raw/supporting-docs` mounted read-only at `SUPPORTING_DOCS_DIR`, placeholder `DATA_DIR`), and add `LEGILO_SRC` and `LEGILO_PORT` to `.env.example`. Verify `docker compose --profile ingest up -d legilo` starts and `curl localhost:8100/<a downloaded id>/documents` returns Markdown, and that plain `docker compose up` does not build it
- [ ] 4.2 Replace `LegiloFetcher` with a local Legilo converter: a reachability check that fails naming `LEGILO_URL`, an uncached session with `legilo_timeout`, and for each dataset with supporting files and no `_result.json`, writing `markdown/<id>/<basename>.md` for each success and `_result.json` with Legilo's errors. A dataset-level HTTP error or timeout leaves no `_result.json`. Warn when a basename occurs twice in the stored files. Verify unit tests with a mocked Legilo for success, a per-file error, a timeout, a duplicate basename, an unreachable service, and that a second run makes no requests

## 5. Build stage

- [ ] 5.1 Implement building a bundle from the raw store for the first N IDs (or all): error if fewer than N are complete; run `EntityExtractor` on the stored metadata and `ConceptHierarchyFetcher` with the stored-only lookup; convert where needed; turn cached Markdown into `Document`s with `uri`, `title` and `filename`; then call `build_concepts` and `write_bundle` with the output directory. Verify unit tests with a fixture raw store (two datasets from `tests/data`, one with Markdown and one recorded failure) that check document concepts hold the full Markdown, the failed file is missing, and building into a second directory leaves the first unchanged
- [ ] 5.2 Remove `DocumentTruncator`, `LegiloFetcher._is_prose`, `PipelineBuilder` and `src/serka/pipelines.py` along with their tests, and update `tests/test_okf_bundle.py` to the new build. Verify `grep -rn "DocumentTruncator\|PipelineBuilder\|legilo_pat\|LEGILO_PAT" src tests scripts` finds nothing, and `uv run pytest tests -m "not integration"` and `ruff check` pass
- [ ] 5.3 Add `scripts/build-bundle.py N|all [--out DIR]` (default `BUNDLES_DIR/<N>` or `BUNDLES_DIR/full`), which prints the concept counts and conversion error count. Verify `uv run scripts/build-bundle.py 20` writes `bundles/20/` and a second run makes no Legilo requests

## 6. Load, one-command ingest and docs

- [ ] 6.1 Make `scripts/load-bundle.py [DIR]` load the given directory, defaulting to `OKF_BUNDLE_DIR`, and verify that loading `bundles/20` and then a different bundle leaves search returning only the second bundle's concepts
- [ ] 6.2 Rewrite `scripts/ingest-data.py [N|all] [--ids-file F] [--no-load]` as download, build into `BUNDLES_DIR/<N>`, then load, and verify `uv run scripts/ingest-data.py 20` produces a searchable index
- [ ] 6.3 Update `scripts/smoke-test.py` to use a temporary `RAW_DIR` and `BUNDLES_DIR`, require the local Legilo for the supporting-document checks (skipped with a message when it can't be reached, in place of the `LEGILO_PAT` check), and drop `scripts/test_legilo.py`. Verify `uv run scripts/smoke-test.py` passes with Legilo running and skips only the supporting-document checks without it
- [ ] 6.4 Update `terraform/scripts/setup.sh` to clone Legilo at `LEGILO_REF` (default `supporting-docs-md`), set `LEGILO_SRC`, start the `ingest` profile, and run `ingest-data.py 100`, failing with a clear log line if the clone fails. Verify with `bash -n` and by reading the generated `.env` section
- [ ] 6.5 Update `README.md` and `CONTRIBUTING.md` for the three stages, the raw store layout, the local Legilo setup and the removal of `LEGILO_PAT`, and verify every documented command runs as written against the 20 bundle

## 7. Rollout

- [ ] 7.1 Download, build and load 20 datasets. Record download time, raw store size, conversion time and error count, bundle concept counts, chunk count and load time in the change's `rollout.md`, and verify a handful of search and AI Summary queries return supporting-document passages
- [ ] 7.2 Repeat for 100 datasets, record the same figures in `rollout.md`, and extrapolate disk use, conversion time and embedding cost for the full collection. Verify that the extrapolation is in `rollout.md` and that the user has agreed to the full run
- [ ] 7.3 Download, build and load the full collection, record the same figures and the slowest or failing conversions in `rollout.md`, and verify search works across the full index

## Workflow follow-up

- Push or merge the Legilo `supporting-docs-md` branch to `NERC-CEH/legilo` before deploying, so `setup.sh` can clone it.
- Archive the change once the rollout is recorded and reviewed.
