from typing import Annotated, Any, Literal, Optional

from app import catalogue, geolocator, logger, mcp
from catalogue import CatalogueError, Filters
from fastmcp.exceptions import ToolError
from geopy.location import Location
from models import BoundingBox, GeoCodedLocation


@mcp.tool()
def search(
	query: Annotated[
		Optional[str],
		"Words or a phrase to rank passages by full-text and semantic relevance. Optional when sort_by is given.",
	] = None,
	sort_by: Annotated[
		Optional[Literal["citations", "published"]],
		"Rank concepts by citation count or publication date instead of returning every matching passage.",
	] = None,
	order: Annotated[Literal["ascending", "descending"], "Sort order for sort_by (default descending)."] = "descending",
	type: Annotated[
		Optional[str],
		"Only concepts of this OKF type: 'dataset', 'document' (a dataset's supporting file), 'person', "
		"'organisation', 'grant', 'theme' or 'ontology'.",
	] = None,
	theme: Annotated[
		Optional[str],
		"Only datasets (and their documents) with this theme: a theme concept id (e.g. 'themes/1a2b3c4d5e6f') "
		"or a theme title. Also matches every narrower theme.",
	] = None,
	linked: Annotated[
		Optional[str],
		"Only concepts whose file links this concept id, e.g. '/people/0000-0002-1825-009X' for the "
		"datasets that person contributed to.",
	] = None,
	bounding_box: Annotated[
		Optional[BoundingBox],
		"Only datasets (and their documents) whose extent overlaps this area, expanded by about 20%. "
		"Use geocode_location to get one for a place name.",
	] = None,
	published_after: Annotated[Optional[str], "ISO date (YYYY-MM-DD): only datasets published on or after it."] = None,
	published_before: Annotated[Optional[str], "ISO date (YYYY-MM-DD): only datasets published on or before it."] = None,
	min_citations: Annotated[Optional[int], "Only datasets cited at least this many times."] = None,
	limit: Annotated[int, "Maximum number of hits to return."] = 25,
) -> dict[str, Any]:
	"""Search the EIDC catalogue: datasets, their supporting documents, people, organisations, grants,
	themes and the ontology concepts that explain roles and relations.

	Each hit is {chunk_id, text, score, concept: {id, type, title, description, resource, tags,
	citations?, published?}}: a passage of a concept file and that concept's summary. Call `read`
	with a concept id, or with any /... link in a passage, to get the whole file. The result is
	{hits, total, warnings}.

	- query only: hybrid full-text and semantic ranking, highest score first, one hit per passage,
	  so one concept can appear several times. `total` counts candidate passages, not concepts:
	  use `aggregate` to count or rank datasets, people and other concepts.
	- sort_by only (no query): every concept matching the filters, one hit per concept, sorted
	  exactly; `total` counts those concepts. Use it for questions like "the most cited dataset"
	  (type='dataset', sort_by='citations', limit=1) or "the newest datasets on a theme".
	- query and sort_by: sorts only the concepts most relevant to the query (a window of at least
	  50, one hit per concept), so it is approximate. When the topic is a catalogue theme, prefer
	  theme=<theme> with no query, which sorts every matching dataset exactly.

	Theme, bounding box, date and citation filters only match datasets and their documents.
	Search again with different words or filters when the first results are not enough.
	"""
	logger.info(f'search: "{query}" [sort_by={sort_by}, type={type}, theme={theme}, linked={linked}]')
	try:
		filters = Filters(
			type=type,
			theme=catalogue.resolve_theme(theme) if theme else None,
			linked=linked,
			bounding_box=bounding_box,
			published_after=published_after,
			published_before=published_before,
			min_citations=min_citations,
		)
		return catalogue.search(query, sort_by, order, filters, limit).dump()
	except CatalogueError as e:
		raise ToolError(str(e)) from e


@mcp.tool()
def aggregate(
	group_by: Annotated[
		Optional[Literal["person", "organisation", "grant", "funder", "theme", "year", "type"]],
		"Group the matching datasets by contributor person or organisation, grant, funder (via grants), "
		"theme or publication year; or count every concept by type. Omit for a single total.",
	] = None,
	role: Annotated[
		Optional[str],
		"With group_by person or organisation: only contributors with this role, e.g. 'author', "
		"'contact-person', 'data-curator' (custodian), 'publisher', 'rights-holder'.",
	] = None,
	sort_by: Annotated[
		Literal["datasets", "citations"],
		"Order groups by their number of datasets (default) or by the summed citations of those datasets.",
	] = "datasets",
	query: Annotated[
		Optional[str],
		"Only count datasets whose text or supporting documents contain any of these words (full-text "
		"match, not semantic similarity). Not combinable with person, organisation, grant, funder or "
		"theme groups: use a theme filter for a topic instead.",
	] = None,
	type: Annotated[
		Optional[str],
		"With no group_by: count concepts of this OKF type instead of datasets ('document', 'person', "
		"'organisation', 'grant', 'theme', 'ontology').",
	] = None,
	theme: Annotated[
		Optional[str],
		"Only datasets with this theme (a theme concept id or title), including narrower themes.",
	] = None,
	linked: Annotated[Optional[str], "Only datasets whose file links this concept id, e.g. '/people/...'."] = None,
	bounding_box: Annotated[
		Optional[BoundingBox], "Only datasets whose extent overlaps this area, expanded by about 20%."
	] = None,
	published_after: Annotated[Optional[str], "ISO date (YYYY-MM-DD): only datasets published on or after it."] = None,
	published_before: Annotated[Optional[str], "ISO date (YYYY-MM-DD): only datasets published on or before it."] = None,
	min_citations: Annotated[Optional[int], "Only datasets cited at least this many times."] = None,
	limit: Annotated[int, "Maximum number of groups to return (person, organisation, grant, funder, theme)."] = 10,
) -> dict[str, Any]:
	"""Count and rank over the whole EIDC catalogue, exactly, in one call. Use it for questions such
	as "how many datasets are there?", "how many datasets mention ozone?", "which author contributed
	to the most datasets?", "who is the most cited author?", "which funder funds the most freshwater
	datasets?" or "how many datasets were published each year?". Never count search hits instead.

	The result is {total, citations?, groups?, total_groups?, warnings}.

	- no group_by: `total` is the number of matching datasets (or concepts of `type`), and
	  `citations` the sum of those datasets' citation counts.
	- person, organisation, grant, funder, theme: `groups` are the related concepts, each
	  {id, title, datasets, citations}: the number of distinct matching datasets it is related to
	  and their summed citations, ordered by sort_by. `total_groups` is how many such concepts there
	  are, and `total` how many matching datasets have at least one. A theme counts the datasets of
	  its narrower themes too. Pass a group's id to `read` for details.
	- year: one group per publication year, in year order, with its datasets and citations.
	- type: the number of concepts of each type in the catalogue ({id, title, concepts}).

	`query` counts full-text matches (datasets that mention the words, in their own text or a
	supporting document, each counted once), not semantic similarity.

	Filters work as in `search`. When stating a number, say what was counted (for example
	"datasets with this person as an author").
	"""
	logger.info(f'aggregate: group_by={group_by} role={role} query="{query}" [type={type}, theme={theme}]')
	try:
		filters = Filters(
			type=type,
			theme=catalogue.resolve_theme(theme) if theme else None,
			linked=linked,
			bounding_box=bounding_box,
			published_after=published_after,
			published_before=published_before,
			min_citations=min_citations,
		)
		return catalogue.aggregate(group_by, role, sort_by, query, filters, limit).dump()
	except CatalogueError as e:
		raise ToolError(str(e)) from e


@mcp.tool()
def read(
	id: Annotated[
		str,
		"A concept id such as 'datasets/<eidc-id>' or '/people/0000-0002-1825-009X' (a leading '/' and "
		"'.md' are optional), or an index such as 'ontology/index' or 'datasets/index'.",
	],
) -> str:
	"""Read a whole concept file from the catalogue: YAML frontmatter (type, title, description,
	resource, tags and, for datasets, published, citations, bbox, themes) and the markdown body.

	Bodies link related concepts with /... links, naming each relation next to the link. Read
	'ontology/index' for the meaning of every type, contributor role and relation predicate.
	"""
	logger.info(f"read: {id}")
	try:
		return catalogue.read(id)
	except CatalogueError as e:
		raise ToolError(str(e)) from e


@mcp.tool()
def geocode_location(location: str) -> GeoCodedLocation:
	"""Geocode a UK place name to geographic boundaries.

	Args:
	    location: A UK place name, city, region, or geographic feature.

	Returns:
	    GeoCodedLocation with display name and BoundingBox.
	"""
	result: Location = geolocator.geocode(location, country_codes="GB")
	if result is None or "boundingbox" not in result.raw:
		raise ToolError(f"Could not geocode location '{location}'")
	boundary: BoundingBox = BoundingBox.from_nominatim(result.raw["boundingbox"])
	return GeoCodedLocation(name=result.raw["display_name"], boundary=boundary)
