# search-results Specification

## Purpose

Defines how the Results page shows chunk-level search hits grouped by the OKF concept they belong to, so each concept appears once with its most relevant passage first.

## Requirements

### Requirement: Hits are grouped by concept
The Results page SHALL group the hits from `/v1/query/semantic` by concept ID. Each group SHALL appear once, and groups SHALL be ordered by the score of their best hit, highest first.

#### Scenario: Two chunks from one dataset
- **WHEN** the response holds hits ranked 1 and 3 from dataset A and hit 2 from dataset B
- **THEN** the page shows one group for A followed by one group for B

### Requirement: Each group leads with its best passage
A group SHALL show the concept's type, title and description, and the text of its highest-scoring hit. Its other hits SHALL be collapsed behind a control that states how many more passages there are, and SHALL be shown in score order when expanded.

#### Scenario: Collapsed passages
- **WHEN** a group has 3 hits
- **THEN** it shows the best hit's text and a control saying there are 2 more passages
- **AND** activating the control shows the other 2 passages in score order

#### Scenario: Single hit
- **WHEN** a group has 1 hit
- **THEN** no expand control is shown

### Requirement: Groups link to the catalogue
When a concept has a `resource`, its group title SHALL link to it. A supporting-document group SHALL also link to the dataset it belongs to.

#### Scenario: Dataset group
- **WHEN** a dataset group is shown
- **THEN** its title links to the dataset's EIDC catalogue page

#### Scenario: Document group
- **WHEN** a group for a supporting document of dataset A is shown
- **THEN** it links to dataset A

### Requirement: Types are shown from OKF types
Each group SHALL show a type label and icon chosen from its concept's OKF `type`. An unknown type SHALL be shown with a generic label and icon, not hidden. The type filter SHALL offer the OKF types and send the chosen one as `type`.

#### Scenario: Unknown type
- **WHEN** a hit's concept has a type the UI does not know
- **THEN** its group is shown with a generic type label

#### Scenario: Filter by type
- **WHEN** the user picks "Person" in the type filter
- **THEN** the search is re-run with `type=person`
