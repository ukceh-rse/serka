# Spec Delta

## MODIFIED Requirements

### Requirement: Ingest writes a conformant OKF bundle
Ingest SHALL write the catalogue as an OKF v0.2 bundle in the local directory chosen for the build, built from the raw store. Every non-reserved `.md` file SHALL have parseable YAML frontmatter with a non-empty `type`, and the bundle-root `index.md` SHALL declare `okf_version: "0.2"`.

#### Scenario: Conformance
- **WHEN** ingest finishes for any set of datasets
- **THEN** every `.md` file in the bundle other than `index.md` and `log.md` has frontmatter with a non-empty `type`

#### Scenario: Version declared
- **WHEN** the bundle root `index.md` is read
- **THEN** its frontmatter contains `okf_version: "0.2"` and nothing else

### Requirement: Supporting documents hold their extracted text
A supporting-document concept SHALL hold, in full, the Markdown that the local Legilo service produced from the original file as its body, with the file name as its `title` and the file's media type in its frontmatter. It SHALL be placed under its dataset's path.

#### Scenario: PDF text
- **WHEN** a dataset `abc` has a supporting file `methods.pdf` with extractable text
- **THEN** a concept under `datasets/abc/` has `type: document`, `title: methods.pdf`, `media_type: application/pdf`, and Legilo's Markdown for the file as its body

#### Scenario: Same file name on two datasets
- **WHEN** two datasets each have a supporting file named `readme.txt`
- **THEN** the bundle contains two separate document concepts

#### Scenario: Long document
- **WHEN** Legilo's Markdown for a supporting file is longer than 45,000 characters
- **THEN** the concept body holds all of it

#### Scenario: Tables kept
- **WHEN** a supporting file's Markdown contains a table
- **THEN** the concept body contains the table as Markdown

### Requirement: Re-ingest leaves no stale concepts
Each build SHALL replace the bundle in its output directory with the build's output, so entities that are not in the build do not remain as concept files there. Bundles in other directories SHALL be left unchanged.

#### Scenario: Smaller run
- **WHEN** a build of 10 datasets is followed by a build of 5 datasets into the same directory
- **THEN** that directory contains only the second build's datasets and the people, organisations, themes, grants, documents and ontology concepts they use

#### Scenario: Other bundles untouched
- **WHEN** a build writes to `bundles/20`
- **THEN** `bundles/100` is unchanged
