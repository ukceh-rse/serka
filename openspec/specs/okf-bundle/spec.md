# okf-bundle Specification

## Purpose

Defines the local Open Knowledge Format bundle that ingest produces from the EIDC catalogue and Legilo, so people, agents and the search index all read the same plain markdown knowledge.

## Requirements

### Requirement: Ingest writes a conformant OKF bundle
Ingest SHALL write the catalogue as an OKF v0.2 bundle in the local directory chosen for the build, built from the raw store. Every non-reserved `.md` file SHALL have parseable YAML frontmatter with a non-empty `type`, and the bundle-root `index.md` SHALL declare `okf_version: "0.2"`.

#### Scenario: Conformance
- **WHEN** ingest finishes for any set of datasets
- **THEN** every `.md` file in the bundle other than `index.md` and `log.md` has frontmatter with a non-empty `type`

#### Scenario: Version declared
- **WHEN** the bundle root `index.md` is read
- **THEN** its frontmatter contains `okf_version: "0.2"` and nothing else

### Requirement: Each catalogue entity is one concept file
Ingest SHALL write one concept file per dataset, person, organisation, grant, theme and supporting document, with `type` set to `dataset`, `person`, `organisation`, `grant`, `theme` or `document`. Concept IDs SHALL be derived from source identifiers, so re-ingesting the same entity writes to the same path.

#### Scenario: Dataset concept
- **WHEN** EIDC dataset `1c2fe14e-...` is ingested
- **THEN** the bundle contains `datasets/1c2fe14e-....md` with `type: dataset`

#### Scenario: Stable IDs
- **WHEN** the same dataset is ingested twice
- **THEN** both runs write its people, organisations, themes and documents to the same concept paths

#### Scenario: Shared entity
- **WHEN** two datasets have the same author
- **THEN** the bundle contains one concept file for that person, linked from both datasets

### Requirement: Concepts carry the recommended OKF frontmatter
Every concept SHALL have `title` and, where the source provides them, `description`, `resource` (the entity's canonical URI, such as its EIDC catalogue page) and `tags`. A dataset concept SHALL also carry its publication date, citation count, bounding box and theme concept IDs as extension keys, and its contributors (each concept ID with its role names), grant concept IDs and funder concept IDs. These relation keys SHALL name the same concepts and roles that its body links.

#### Scenario: Dataset frontmatter
- **WHEN** a dataset with a bounding box, publication date, citation count and two keywords is ingested
- **THEN** its frontmatter has `title`, `description`, `resource` set to its catalogue URI, `tags`, and extension keys for the date, citations, bounding box and theme IDs

#### Scenario: Relation keys
- **WHEN** a dataset has an author who is also its contact, a custodian organisation, and a grant from a funder
- **THEN** its frontmatter lists the author's concept ID with roles `author` and `contact-person`, the organisation with role `data-curator`, the grant's concept ID under grants and the funder's concept ID under funders
- **AND** its body links each of them

#### Scenario: Missing source field
- **WHEN** a person has no affiliation or description in the source record
- **THEN** their concept is still written, without those keys

### Requirement: Relations are written as links with their meaning in the text
Relations between entities SHALL be written as bundle-relative markdown links (starting with `/`) in the body. The surrounding text SHALL name the relation, such as a contributor's role or a related-dataset predicate, and SHALL link that role or predicate to its ontology concept.

#### Scenario: Contributor role
- **WHEN** a dataset has an author and a custodian
- **THEN** its body links each person or organisation concept, and each link is accompanied by its role name linked to that role's `ontology/` concept

#### Scenario: Related dataset
- **WHEN** a dataset is part of another dataset
- **THEN** its body links the parent dataset concept with text naming the relation

#### Scenario: Supporting document
- **WHEN** a dataset has a supporting PDF
- **THEN** the dataset body links the document concept, and the document concept links back to the dataset

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

### Requirement: Themes record their hierarchy
A theme concept SHALL link to its broader theme concepts. A dataset concept's theme IDs SHALL include each of its themes and every broader theme above them.

#### Scenario: Theme ancestors
- **WHEN** a dataset has the theme "Freshwater fish", whose broader theme is "Biodiversity"
- **THEN** the dataset's theme IDs include both themes, and the "Freshwater fish" concept links to the "Biodiversity" concept as broader

### Requirement: The bundle describes its own vocabulary
The bundle SHALL contain `ontology/` concepts, generated from the DOO ontology, for each concept type, contributor role and relation predicate used in the bundle. Each one SHALL give the term's plain-language meaning and its DOO identifier.

#### Scenario: Role concept
- **WHEN** any dataset in the bundle has a custodian
- **THEN** the bundle contains an `ontology/` concept for the custodian role, with its meaning and DOO identifier

#### Scenario: Unused term
- **WHEN** no dataset uses a DOO predicate
- **THEN** the bundle has no concept for it

### Requirement: Index files support browsing
Ingest SHALL write an `index.md` at the bundle root and in each top-level directory. Each index SHALL link the concepts or subdirectories it contains, each with a one-line description.

#### Scenario: Root index
- **WHEN** the bundle root `index.md` is read
- **THEN** it links each top-level directory, including `ontology/`, with a short description

#### Scenario: Ontology index
- **WHEN** `ontology/index.md` is read
- **THEN** it links every ontology concept with its one-line meaning

### Requirement: Re-ingest leaves no stale concepts
Each build SHALL replace the bundle in its output directory with the build's output, so entities that are not in the build do not remain as concept files there. Bundles in other directories SHALL be left unchanged.

#### Scenario: Smaller run
- **WHEN** a build of 10 datasets is followed by a build of 5 datasets into the same directory
- **THEN** that directory contains only the second build's datasets and the people, organisations, themes, grants, documents and ontology concepts they use

#### Scenario: Other bundles untouched
- **WHEN** a build writes to `bundles/20`
- **THEN** `bundles/100` is unchanged
