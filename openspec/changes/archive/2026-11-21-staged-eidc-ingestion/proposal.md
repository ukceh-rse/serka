# Proposal

## Why

Ingest currently fetches EIDC records, calls the hosted Legilo service and writes the OKF bundle in one run, and each run replaces the bundle. The original supporting files are never kept, the hosted Legilo returns plain text rather than Markdown, and growing from a small test set to the full EIDC collection means fetching and converting everything again each time. We want to build bundles of 20, 100 and then all datasets from one local copy of the source material, convert supporting documents to Markdown with the local Legilo (`supporting-docs-md` branch), and load whichever bundle we want into Redis.

## What Changes

- Ingest is split into three stages that run on their own:
  1. **Download** writes a local raw store: an ordered dataset ID list, each dataset's EIDC metadata JSON, its unzipped original supporting files from `https://data-package.ceh.ac.uk/sd/<id>.zip`, and the GEMET broader-concept lookups. Downloads are incremental: anything already in the store is skipped unless a refresh is asked for.
  2. **Build** converts the first N datasets of the raw store (or all of them) into an OKF bundle in its own directory, such as `bundles/20/`, `bundles/100/`, `bundles/full/`. Supporting-document Markdown comes from a local Legilo container and is cached in the raw store, so rebuilding a bundle does not convert again. Building needs no EIDC, data-package or GEMET access.
  3. **Load** reads a bundle directory given on the command line into Redis.
- The dataset order is a seeded shuffle of every published EIDC dataset, with the IDs of an optional ids file placed first. The first 20 datasets are always within the first 100, which are always within the full collection.
- Legilo runs locally: a `legilo` service in `compose.yaml` (opt-in profile) built from a local checkout of the Legilo `supporting-docs-md` branch, with the raw store's supporting files mounted as its documents directory.
- **BREAKING**: the hosted Legilo service and `LEGILO_PAT` are no longer used. Ingest needs the local Legilo container for supporting documents.
- **BREAKING**: building a bundle writes only that bundle's directory. A bundle is no longer a single shared `OKF_BUNDLE_DIR` replaced by every run.
- Supporting-document concepts hold Legilo's Markdown in full. Truncation to 45,000 characters and the whitespace "prose" filter are removed. Per-file conversion failures are recorded in the raw store and do not stop the build.
- `scripts/ingest-data.py` stays as a one-command wrapper (download, build, load) for the deploy setup and the smoke test.
- The rollout to 20, 100 and the full collection is part of the work, with time, disk and embedding cost recorded at each size.

## Capabilities

### New Capabilities

- `catalogue-ingest`: the download stage and the raw store (dataset order, metadata, original supporting files, GEMET lookups, cached Markdown and conversion errors), the local Legilo conversion, and building and loading a chosen bundle.

### Modified Capabilities

- `okf-bundle`: the bundle is built from the raw store into a chosen directory rather than replaced by every ingest run, and supporting-document concepts hold the Markdown produced by the local Legilo.

## Impact

- **Depends on** `replace-neo4j-with-redis-okf` being archived first: `okf-bundle` is introduced by that change and is not yet in `openspec/specs/`.
- **Code**: `src/serka/fetchers.py` (EIDC, data-package, GEMET and local Legilo access), `src/serka/pipelines.py`, `src/serka/graph/extractors.py` (`DocumentTruncator` removed), `src/serka/okf/writer.py`, `src/serka/settings.py` (raw store, bundles directory and Legilo URL; `legilo_pat` removed), a new raw store module, and scripts `ingest-data.py`, `load-bundle.py`, `smoke-test.py`, plus new download and build scripts.
- **Infrastructure**: `compose.yaml` gains a `legilo` service, which needs a local Legilo checkout (`LEGILO_SRC`). `terraform/scripts/setup.sh` needs that checkout too, or it cannot build supporting documents.
- **Configuration and docs**: `.env.example`, `.gitignore` (`raw/`, `bundles/`), `README.md`, `CONTRIBUTING.md`.
- **Disk and cost**: the raw store holds every original supporting file, which can be large for the full collection. Loading the full bundle embeds every chunk with Bedrock.
