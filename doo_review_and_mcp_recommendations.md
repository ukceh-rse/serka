# DOO support on `doo-integration`: review and recommendations

Reviewed 2026-10-27 against `main...doo-integration` (19 commits, up to `c49621b`), the
published [Digital Objects Ontology](https://nerc-ceh.github.io/digital-objects-ontology)
(now **v0.3.3**, not the v0.2.1 the original plan was written against), live EIDC records
(the 10 IDs in `tests/smoke/datasets.txt`), and the MCP 2025-11-25 tools spec.

## Verdict

**The foundation is right, but this isn't yet a reasonable implementation of DOO.**

The branch made the right architectural call. It layers DOO typing over the existing
Neo4j and hybrid-search stack, adds generic predicate-driven tools (`search`, `get_relations`,
`get_contributors`, `find_by_contributor`, `get_content`), and provides a `doo://context`
discovery resource. The UI and smoke test follow that model consistently. Three gaps
stop it from being DOO-conformant:

1. **Data is silently dropped during ingestion.** Wrong EIDC keys mean dataset-to-dataset
   relationships, contact points, rights holders and theme keywords are never extracted.
   Funding, a core DOO area, isn't modelled at all, even though EIDC supplies it. All of
   this was verified on live records (see §1).
2. **Roles don't follow DOO's pattern.** DOO uses reified `pro:RoleInTime` nodes whose
   `pro:withRole` points at a role *individual* (`pro:author`, `scoro:data-curator`, …).
   Serka puts role *classes* (`scoro:AuthorshipRole`) and plain properties
   (`dcterms:publisher`) in the same slot (see §2).
3. **The MCP output only looks like JSON-LD.** Entities use `id`/`type` rather than `@id`/`@type`,
   with no `@context`. `Entity.properties` returns raw Neo4j keys (`publication_date`), not
   the DOO terms its docstring promises. No JSON-LD processor can expand the output (see §3).

Fixing §1 and §2 needs a re-ingest. §3 only touches the MCP layer. Each is a few days of
work at most.

---

## 1. Correctness bugs (verified)

| # | Where | Problem | Evidence |
|---|---|---|---|
| 1.1 | `src/serka/graph/extractors.py:144-148` `_extract_relations` | Reads `rel["identifier"]` and `rel["associationType"]`. EIDC uses `rel["target"]` and `rel["relation"]`. **No `RELATION` dataset↔dataset edges are ever written.** | Record `1c2fe14e…` has 2 `relationships`; `EntityExtractor().run()` returns `RELATION: 0`. 5 of the 10 smoke records have relationships. The test fixture has none, so the bug is invisible. |
| 1.2 | same | Even after the fix, EIDC gives full URIs (`http://purl.org/dc/terms/isPartOf`) while the default and the citation predicate are CURIEs (`dcterms:relation`). `get_relations(predicate="dcterms:isPartOf")` and the `explore_dataset` prompt would never match. | Live record values above. |
| 1.3 | `extractors.py:8-14` `_PARTY_FIELDS` | Uses `pointsOfContact`, but the live EIDC API now returns `contactPoints` (records cached before the rename still use `pointsOfContact`, so both must be read). `rightsHolders` is missing, though `ROLE_TERMS` maps `rightsHolder`. Result: no contact or rights-holder associations. | All 10 smoke records have `contactPoints` (role `pointOfContact`). 9 of 10 have `rightsHolders`. 0 of 10 have `pointsOfContact`. |
| 1.4 | `extractors.py` `_extract_concepts` | Reads `topicCategories`/`keywordsOther`/`keywordsPlace` but not `keywordsTheme` (present in 7 of 10 records), `keywordsProject` or `keywordsInstrument`. | Field counts from live records. |
| 1.5 | `extractors.py:97-118` `_extract_parties` | When an author entry has both an ORCID and a ROR, the **organisation** also gets an `ASSOCIATED_WITH{role:"author"}` edge. `get_contributors` then lists the affiliation as an author. In DOO, the person holds the role and the org is reached via `org:memberOf`. | Logic inspection. Record `1c2fe14e…` yields 5 associations for 4 parties. |
| 1.6 | `mcp-server/src/serka-mcp/prompts.py` `explore_author_work` | Tells the agent to call `search` with `types=['foaf:Person']`. That parameter doesn't exist; it's `return_type='foaf:Person'`. | Compare with the `search` signature in `tools.py`. |
| 1.7 | `mcp-server/.../tools.py` `_props_to_entity` | `Entity.properties` says "mapped to DOO terms", but `PROPERTY_TERMS` is never applied. Keys come back raw. | Code inspection. |
| 1.8 | `extractors.py` boundary extraction | Logs `ERROR … 'boundingBoxes'` for every record without a bbox. This is noise, not a failure. | Seen while running the extractor on `1c2fe14e…`. |

Add a fixture built from a real EIDC record (for example `1c2fe14e…`), with `relationships`,
`contactPoints`, `rightsHolders`, `funding` and `keywordsTheme`, to `tests/test_extractors.py`.
1.1, 1.3 and 1.4 would all have been caught by it.

## 2. Ontology fidelity gaps

### 2.1 Roles: adopt DOO's role-in-time pattern

DOO v0.3.3 models agent roles as:

```
foaf:Agent  --pro:holdsRoleInTime-->  pro:RoleInTime
pro:RoleInTime  --pro:withRole-->     <role individual, e.g. pro:author>
pro:RoleInTime  --pro:relatesToEntity--> dcat:Dataset (prov:Entity)
```

The role classes (`scoro:AuthorshipRole`, `scoro:DataRole`, `pro:PublishingRole`, …) are
the *types* of those individuals. `ROLE_TERMS` mixes three different kinds of term:

- role classes (`scoro:AuthorshipRole`)
- plain properties (`dcterms:publisher`, `dcterms:rightsHolder`)
- `pro:RoleInTime`, the reified node's class, used as a fallback "role"

It also lets `author` and `originator` collapse to the same value. Suggested mapping, using
individuals DOO declares:

| EIDC role | `pro:withRole` individual | its class |
|---|---|---|
| author, coAuthor | `pro:author` | `pro:PublishingRole` |
| originator | `scoro:data-creator` | `scoro:DataRole` |
| publisher | `pro:publisher` | `pro:PublishingRole` |
| distributor, distributorContact | `pro:distributor` | `pro:PublishingRole` |
| custodian | `scoro:data-curator` | `scoro:DataRole` |
| rightsHolder | `scoro:rights-holder` | `scoro:OrganizationalRole` |
| pointOfContact | `scoro:contact-person` | `scoro:OrganizationalRole` |
| principalInvestigator | `scoro:principal-investigator` | `scoro:InvestigationRole` |
| *(unknown)* | `pro:contributor` | `pro:PublishingRole` |

You don't need to reify in Neo4j. `ASSOCIATED_WITH{role}` is already the role-in-time
node collapsed onto an edge. Store the individual's CURIE and expose both values in the
MCP output: `Attribution.role` (the individual) and `Attribution.role_type` (the class).
Then `get_contributors(role=…)` can filter by either. Filtering on a class means "any
individual of that class", which is a small instance of the ontology expansion idea in §3.6.

### 2.2 Funding: in DOO, in EIDC, not in Serka

The plan said there was no EIDC source data for frapo. That's wrong: 6 of 10 smoke records
have `funding[]` with `funderName`, `funderIdentifier` (ROR) and `awardNumber`. Model it as:

- `Organisation` (already exists) + label/type `frapo:FundingAgency` (a subclass of `foaf:Organization`)
- new `Grant` node → `frapo:Grant`, with `frapo:hasGrantNumber`. Use `awardURI` as the `@id`
  when present, otherwise a synthetic `{funderIdentifier}#{awardNumber}`.
- `Dataset -[:RELATION{predicate:"doo:originatingGrant"}]-> Grant`
- `FundingAgency -[:RELATION{predicate:"frapo:awards"}]-> Grant`

The existing generic `RELATION{predicate}` pattern handles this with no new MCP tools.
"Which NERC-funded datasets…" becomes a two-hop `search`/`get_relations` query.

### 2.3 Smaller term mismatches in `PROPERTY_TERMS`

| Serka property | Current term | Problem | Suggested |
|---|---|---|---|
| `citations` (an int count) | `dcterms:relation` | `dcterms:relation` links to a resource, not a count | Drop the mapping (it's derivable from `dcterms:isReferencedBy` edges), or use a clearly local term such as `serka:citationCount` |
| `south/north/west/east_boundary` | `geo:hasBoundingBox` ×4 | Four floats can't each be a bounding box | Emit one `dcat:bbox` WKT literal (`POLYGON((…))`), or a `geo:hasBoundingBox` object with `geo:asWKT` |
| `temporal_start` / `temporal_end` | `dcterms:temporal` ×2 | Both keys collapse to one term, so start and end become indistinguishable | `dcterms:temporal` → `{ "@type": "dcterms:PeriodOfTime", "dcat:startDate": …, "dcat:endDate": … }` |
| `resource_type` | `dcterms:type` | Fine, but the value is a bare string | Prefer a vocabulary URI where EIDC has one |
| `doo:isDescribedByPublication` | unused | DOO's own property for a `dcat:Resource` → `fabio:Expression` (data papers) | Consider it for supporting docs or data papers instead of generic `dcterms:references` |

Also available in EIDC and easy to add: `distributionFormats`/`onlineResources` →
`dcat:Distribution` (`dcterms:format`, `dcat:accessURL`), and `keywordsProject` → `foaf:Project`.

### 2.4 One mapping, three copies

`src/serka/ontology.py`, `mcp-server/src/serka-mcp/ontology.py` and `ui/src/ontology.ts`
duplicate the mapping, and they already differ (`to_jsonld` exists only in the first).
Keep a single `ontology/doo-mapping.json` (or a real JSON-LD context file, see §3.1), load
it from Python, and import it into Vite as JSON.

Also add a unit test that loads a cached copy of DOO's `ontology.ttl` with `rdflib`
and checks that every CURIE in `NODE_TYPES`/`ROLE_TERMS` is a declared class or individual.
That test would have caught the role mix-up in §2.1.

---

## 3. Better ways for the MCP server to return ontological types

### What the research found

- **No MCP standard covers semantic or JSON-LD output.** I found no SEP or spec text on
  linked-data tool results. The relevant spec mechanisms are `outputSchema` +
  `structuredContent`, `resource_link`/embedded resource content blocks, and annotations
  ([MCP tools spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)).
  The spec says a tool returning structured content *SHOULD* also return the serialised JSON
  as text, because some clients ignore `structuredContent`.
- **Ontology-backed MCP servers converge on two patterns.** Some are generic SPARQL
  servers. Others, like Serka, have domain tools plus schema discovery. The most developed
  published example, [mcp-proto-okn](https://arxiv.org/abs/2605.30283) (FastMCP, NSF
  Proto-OKN), exposes `get_schema` (classes, predicates and properties) and
  `get_query_template` as **tools**. It returns results with "query-analysis metadata
  and warnings", and adds automatic **ontology expansion**. In its case study,
  expanding one MONDO term to its descendants raised the hit count from 447 datasets to
  over 10,000. [Ontology-to-tools compilation](https://arxiv.org/abs/2602.03439) goes
  further and compiles the T-Box into tool schemas, so that constraints are enforced at
  call time. Other directory projects
  ([ontology-mcp](https://glama.ai/mcp/servers/JiteAgar-Code/ontology-mcp),
  [rdf-kg-mcp planning](https://github.com/rewire-bio/rdf-kg-mcp/issues/1)) return JSON-LD
  descriptors or plan SHACL/PROV-O integration.
- **FastMCP 3.2.4 (the version in `uv.lock`) already derives `outputSchema` from the return
  annotation.** It wraps non-object roots as `{"result": …}` with
  `x-fastmcp-wrap-result`, and passes `ResourceLink` content blocks through unchanged
  ([FastMCP tools docs](https://github.com/prefecthq/fastmcp/blob/main/docs/servers/tools.mdx)).

**Conclusion:** keep pattern (b), domain tools with ontology annotation, which the memory
note had already chosen. Implement it in a way JSON-LD tooling and MCP clients can use.
Suggestions, in priority order:

### 3.1 Make the output real JSON-LD (high value, low cost)

Use Pydantic aliases so the wire format is valid compact JSON-LD, while the Python stays readable:

```python
class Entity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
    id: str = Field(alias="@id")
    type: list[str] = Field(alias="@type")
    ...

class SearchResults(BaseModel):          # object root → no {"result": …} wrapping
    context: str = Field("doo://context", alias="@context")  # or the inline dict
    graph: list[SearchHit] = Field(alias="@graph")
```

- Put `@context` **once per response**, not on every entity. Since `doo://context` isn't
  dereferenceable over HTTP, either inline the small prefix map (about 12 lines) or also
  publish it at a URL.
- Apply `PROPERTY_TERMS` inside `_props_to_entity` (bug 1.7), or put the term mappings
  *in the context* (`"title": "dcterms:title"`) and keep the short keys. The second
  option is better: the output keeps short, LLM-friendly keys and still expands to the
  correct IRIs.
- Add a unit test that runs a `search` response through `pyld.jsonld.expand()` and checks
  the result contains the expected full IRIs.

### 3.2 Return errors as `isError`, not as a successful `Error` object

Every tool returns `Union[X, Error]`. In MCP terms, that's a *successful* result whose
payload happens to describe an error. It also makes every `outputSchema` an `anyOf`.
Raise `fastmcp.exceptions.ToolError` instead, so the client gets `isError: true` and the
LLM self-corrects as the spec intends. The output schema then describes only the success shape.

### 3.3 Carry type semantics in the `outputSchema` itself

Clients and LLMs see `outputSchema` in `tools/list`, *before* calling anything. Two options:

- **Typed subclasses with a discriminated union on `@type`.** Use `DatasetEntity`,
  `PersonEntity`, `ConceptEntity`, `DocumentEntity`, … each with real, documented fields,
  instead of a generic `properties: dict[str, Any]`. That gives the LLM field-level
  descriptions, at the cost of a little more code per type. Recommended: there are only
  about 6 types.
- **Schema annotations** via `json_schema_extra`, e.g. `{"x-rdf-type": "dcat:Dataset"}` on
  the model and `{"x-rdf-property": "dcterms:issued"}` on fields. This is a convention,
  not a standard, but it's harmless and makes the mapping machine-readable from the tool
  listing alone.

### 3.4 Don't rely on resources for discovery: add a `describe_ontology` tool

MCP resources are *application-controlled*. Most clients (Claude Desktop, most agent
frameworks) don't let the model read `doo://context` by itself, so prompts that say
"Step 1: read doo://context" often can't be followed. Following mcp-proto-okn's
`get_schema`:

- Add a `describe_ontology()` **tool** that returns, for each type, predicate and role in use:
  the CURIE, its `rdfs:label`/`rdfs:comment` from DOO or the source vocabulary, and
  instance counts from Neo4j. Definitions matter more to an LLM than a bare prefix map.
- Put a short glossary in `FastMCP("Serka", instructions=…)`, for example: "Types: dcat:Dataset,
  foaf:Person, … Predicates: dcat:theme, dcterms:isPartOf, …". Clients inject it into
  context automatically.
- Keep `doo://context`, but serve it as an actual JSON-LD context document
  (`mime_type="application/ld+json"`).

### 3.5 Link, don't inline, using `resource_link` blocks

For each hit, also emit a `ResourceLink(uri=f"doo://entity/{id}", name=label,
mimeType="application/ld+json")` content block next to the structured payload. Clients
that support resources can then dereference or subscribe to entities, and the
`doo://entity/{uri}` template becomes reachable from tool output.

### 3.6 Ontology-aware query expansion

This is the main lesson from mcp-proto-okn. EIDC concepts come from hierarchical
vocabularies (GEMET, INSPIRE topic categories, NERC vocab server), and roles have class
hierarchies.

- Store `skos:broader` for `Concept` nodes at ingest (fetch once from the vocab services
  and cache). Then let a `theme` filter on `search` or `get_relations` expand to
  descendants. Report the expansion in result metadata, e.g.
  `"expanded": {"gemet:…": 37}`.
- Role filters accept either a class (`scoro:DataRole`) or an individual
  (`scoro:data-curator`). See §2.1.

### 3.7 Return provenance and warnings metadata

Add a small `meta` object to search responses, carrying `return_type` resolution, `hops`
used, filters applied, any expansion, and warnings. One example warning: "date filter
ignored for non-Dataset results", which matches the behaviour fixed in `06b25a2`. This
helps the LLM explain its results and retry sensibly.

### 3.8 Not recommended right now

- **A generic SPARQL tool or a triplestore.** It's heavy, and it would duplicate the
  Neo4j hybrid search. If external interoperability is needed later, export JSON-LD per
  dataset (plan Phase 5) or dump to Turtle, rather than changing the store.
- **Full T-Box-compiled tools.** That approach targets KG *construction*. Serka's MCP
  server is read-only.

---

## 4. Suggested order

1. Fix §1.1–1.6 and add a real-record extractor fixture. → `uv run pytest`
2. Remap roles (§2.1), add funding (§2.2), fix the term mismatches (§2.3), single-source
   the mapping and add the rdflib conformance test (§2.4). Re-ingest.
3. Make the MCP output JSON-LD (§3.1, with a pyld expand test), switch to `ToolError`
   (§3.2), use typed entity subclasses (§3.3).
4. Add the `describe_ontology` tool and server `instructions` (§3.4), then resource links
   (§3.5). Update `prompts.py` to match.
5. Concept hierarchy expansion (§3.6) and response metadata (§3.7).

Also worth updating: the memory note `doo_ontology_integration.md` still says DOO v0.2.1
and "no source data" for frapo. Both are now out of date.

## Sources

- Digital Objects Ontology v0.3.3: https://nerc-ceh.github.io/digital-objects-ontology
- MCP tools spec 2025-11-25 (structured content, output schema, resource links, isError): https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- mcp-proto-okn (FastMCP, schema-inspection tools, ontology expansion): https://arxiv.org/abs/2605.30283 and https://github.com/sbl-sdsc/mcp-proto-okn
- Ontology-to-tools compilation for executable semantic constraints: https://arxiv.org/abs/2602.03439
- ontology-mcp (JSON-LD descriptors from OWL/SHACL/SKOS): https://glama.ai/mcp/servers/JiteAgar-Code/ontology-mcp
- rdf-kg-mcp planning issue (JSON-LD, SHACL, PROV-O): https://github.com/rewire-bio/rdf-kg-mcp/issues/1
- FastMCP tools and structured output docs: https://github.com/prefecthq/fastmcp/blob/main/docs/servers/tools.mdx
- Discussion of outputSchema/structuredContent client support: https://zenn.dev/7shi/articles/20250710-output-schema, https://modelcontextprotocol.io/seps/2106-json-schema-2020-12.md

---

## Implementation status (2026-10-27)

All suggestions above are implemented on `doo-integration` (uncommitted):

| § | Change | Where |
|---|---|---|
| 1.1–1.4 | `relationships[].{relation,target}`, predicates compacted to CURIEs, `contactPoints`, `rightsHolders`, `keywordsTheme` | `src/serka/graph/extractors.py` |
| 1.5 | An organisation holds a role only when the entry names no person; otherwise it's an affiliation | `extractors.py` `_extract_parties` |
| 1.6 | Prompts use `return_type=` and `describe_ontology`/`get_entity` | `mcp-server/src/serka-mcp/prompts.py` |
| 1.7 | Entity properties mapped via the JSON-LD `@context` | `doo_mapping.json` `terms` |
| 1.8 | Missing bbox no longer logged as an error | `extractors.py` |
| 2.1 | Roles mapped to DOO role individuals + classes; `get_contributors` returns `pro:RoleInTime` (`agent` = `@reverse pro:holdsRoleInTime`); role filters accept an individual or a class | `doo_mapping.json`, `tools.py` |
| 2.2 | `funding[]` → `Organisation:FundingAgency`, `Grant`, `doo:originatingGrant`, `frapo:awards` | `extractors.py`, `writers.py` |
| 2.3 | `dcat:bbox` WKT, `dcterms:temporal` → `dcterms:PeriodOfTime` with `dcat:startDate`/`endDate`, citations → `serka:citationCount` (`urn:serka:`) | `entities.py`, `doo_mapping.json` |
| 2.4 | One mapping (`mcp-server/src/serka-mcp/doo_mapping.json`) copied to `src/serka/` and `ui/src/` by `scripts/sync-doo-mapping.py`; `tests/test_ontology.py` checks the copies and conformance against vendored DOO 0.3.3 | |
| 3.1 | Every graph tool returns `{"@context", "@graph", ...}`; entities use `@id`/`@type`; verified with `pyld` expansion | `models.py`, `entities.py` |
| 3.2 | `ToolError` (`isError: true`) instead of `Error` objects | `tools.py` |
| 3.3 | Typed entity models per DOO class with `x-rdf-type` / `x-rdf-property` in the output schema | `models.py` |
| 3.4 | `describe_ontology` tool (definitions + live counts), server `instructions`, `get_entity` tool; `doo://context` served as `application/ld+json` | `tools.py`, `ontology.py` |
| 3.5 | `resource_link` content block per returned entity → `doo://entity/{uri*}` | `tools.py` |
| 3.6 | GEMET `skos:broader` ancestors fetched at ingest (`ConceptHierarchyFetcher`); `search(theme=…)` expands to narrower concepts | `fetchers.py`, `queries.py` |
| 3.7 | `meta` on search: filters, hops, theme expansion, reranking, warnings | `tools.py` |

The conformance test also found that the branch's `dcat` namespace was `https://www.w3.org/ns/dcat#`.
DCAT and DOO use `http://`, so every `dcat:` IRI the branch emitted was wrong. This is now fixed and
guarded by `test_prefix_namespaces_match_doo`.

**Re-ingest required.** The graph gains new nodes and edges, and the full-text index now covers
`Grant`. Because indexes are created `IF NOT EXISTS`, drop `ft_search` (or wipe the DB with
`clean_db.sh`) before running `scripts/ingest-data.py`.

Not done: `keywordsProject` → `foaf:Project`, because EIDC project keywords carry no URI to key
nodes on. Concept hierarchies outside GEMET (NERC/CEH topics, EnvThes) are also not fetched yet.
