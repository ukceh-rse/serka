# Spec Delta

## Purpose

Gets the EIDC catalogue from its sources into Serka in separate stages: a local raw store of original metadata and supporting files, OKF bundles of a chosen size built from that store, and loading a chosen bundle into Redis.

## ADDED Requirements

### Requirement: Download keeps a local raw store
The download stage SHALL write, for each dataset, its EIDC metadata JSON and its original supporting files to a configured local raw store directory, so later stages need no EIDC or data-package access.

#### Scenario: Dataset with supporting documents
- **WHEN** dataset `abc` is downloaded and its supporting-documents zip contains `methods.pdf`
- **THEN** the raw store holds `abc`'s EIDC metadata JSON and the original `methods.pdf` byte for byte

#### Scenario: Dataset without supporting documents
- **WHEN** a dataset has no supporting-documents zip
- **THEN** its metadata is stored, it is recorded as having no supporting files, and the download carries on without an error

### Requirement: Downloads are incremental
The download stage SHALL skip any dataset whose metadata and supporting files are already in the raw store, unless a refresh is requested.

#### Scenario: Growing from 20 to 100
- **WHEN** 20 datasets have been downloaded and a download of 100 is run
- **THEN** only the 80 datasets not yet in the raw store are fetched

#### Scenario: Interrupted download
- **WHEN** a download stops part way and is run again
- **THEN** it fetches only the datasets that were not completely stored, and a partly written dataset is never treated as complete

#### Scenario: Refresh
- **WHEN** a download is run with refresh requested
- **THEN** every selected dataset is fetched again and its stored files replaced

### Requirement: Dataset order is stable and nested
The raw store SHALL keep one ordered list of dataset IDs: the IDs of an optional ids file first, in file order, then every other published EIDC dataset in an order shuffled with a recorded seed. Selecting N datasets in any stage SHALL take the first N of this list.

#### Scenario: Nested subsets
- **WHEN** bundles of 20 and 100 datasets are built from the same raw store
- **THEN** every dataset in the 20 bundle is in the 100 bundle

#### Scenario: Ids file first
- **WHEN** the order is created with an ids file of 10 IDs
- **THEN** the first 10 IDs of the order are those IDs in file order, and none of them appears again later

#### Scenario: Reproducible order
- **WHEN** the order is created twice from the same published dataset list, ids file and seed
- **THEN** both orders are identical

#### Scenario: Order is kept
- **WHEN** a later download runs against a raw store that already has an order
- **THEN** the existing order is reused, and published datasets missing from it are appended at the end

### Requirement: GEMET hierarchy is stored with the raw data
The download stage SHALL store the GEMET broader-concept lookups needed by the stored datasets' themes, so building a bundle makes no GEMET requests.

#### Scenario: Offline build
- **WHEN** a bundle is built with no network access other than the local Legilo service
- **THEN** its themes record their broader GEMET concepts as they would online

### Requirement: Supporting documents are converted to Markdown by the local Legilo
Supporting files SHALL be converted to Markdown by a Legilo service run locally from the `supporting-docs-md` branch, reading the raw store's original files. The hosted Legilo service and its access token SHALL NOT be used.

#### Scenario: Conversion
- **WHEN** dataset `abc`'s stored `methods.docx` is converted
- **THEN** its Markdown, with headings, lists and tables, comes from the local Legilo service

#### Scenario: Local Legilo not running
- **WHEN** a build needs a conversion and the local Legilo service cannot be reached
- **THEN** the build stops with an error naming the Legilo URL, before writing a bundle

### Requirement: Converted Markdown is cached in the raw store
The Markdown for each supporting file SHALL be stored in the raw store once converted, and a build SHALL reuse it rather than convert the file again.

#### Scenario: Rebuild without reconversion
- **WHEN** the 20 bundle is built twice
- **THEN** the second build makes no Legilo requests

### Requirement: Conversion failures are recorded and skipped
A supporting file that cannot be converted SHALL be recorded in the raw store with the reason, left out of the bundle, and SHALL NOT stop the build. A recorded failure SHALL NOT be retried unless a refresh is requested.

#### Scenario: Scanned PDF
- **WHEN** a dataset's supporting files include a scanned PDF that Legilo rejects
- **THEN** the dataset's other documents are in the bundle, the PDF is not, and the raw store records the PDF and Legilo's reason

#### Scenario: Duplicate file name
- **WHEN** a dataset has two supporting files with the same name in different folders
- **THEN** a warning names the dataset and file, and the build carries on

### Requirement: Each bundle size has its own directory
Building SHALL take the number of datasets (or all) and an output directory, and write a bundle of exactly those datasets to that directory without changing any other bundle.

#### Scenario: Side-by-side bundles
- **WHEN** a 100 bundle is built after a 20 bundle, each into its own directory
- **THEN** the 20 bundle's directory is unchanged

#### Scenario: Rebuild replaces only its own bundle
- **WHEN** a bundle is built into a directory that already holds a bundle
- **THEN** that directory holds only the new build's concepts, and a failed build leaves the previous bundle as it was

#### Scenario: Not enough datasets downloaded
- **WHEN** a bundle of 100 is requested but only 20 datasets are in the raw store
- **THEN** the build stops with an error saying how many datasets are available

### Requirement: Load takes a bundle directory
Loading SHALL accept the bundle directory to load as an argument, falling back to the configured bundle directory when none is given.

#### Scenario: Switch bundle
- **WHEN** `bundles/100` is loaded after `bundles/20`
- **THEN** search returns only concepts from the 100 bundle

### Requirement: One command runs every stage
A single ingest command SHALL download, build and load N datasets (or all) in order, so deploy setup and the smoke test need one step.

#### Scenario: Ingest 100
- **WHEN** ingest is run for 100 datasets
- **THEN** the raw store holds at least those 100 datasets, the 100 bundle is built, and it is loaded into Redis
