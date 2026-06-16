from app import mcp


@mcp.prompt()
def find_datasets_for_location(location: str) -> str:
	"""Find EIDC datasets covering a named UK location.

	Chains geocode_location → search with bounding_box → get_relations for themes
	and contributors. Use when a user asks about datasets for a specific area by name.

	Args:
	    location: A UK place name (e.g. "Cairngorms", "River Severn", "Norfolk Broads").
	"""
	return (
		f"Find environmental datasets relevant to '{location}'. "
		"Step 1: use geocode_location to resolve the place name to a bounding_box. "
		"Step 2: use search with that bounding_box to find relevant datasets. "
		"Step 3: for the top datasets, use get_relations with predicate='dcat:theme' to discover their themes, "
		"and get_contributors to identify key researchers. "
		"Step 4: summarise the datasets, their themes, and any notable contributors."
	)


@mcp.prompt()
def explore_author_work(author: str) -> str:
	"""Explore a researcher's contributions to the EIDC catalogue.

	Chains search (types=['foaf:Person']) → find_by_contributor → get_content.
	Use when a user wants to understand a researcher's body of work.

	Args:
	    author: The researcher's name.
	"""
	return (
		f"Explore the published work of '{author}' in the EIDC catalogue. "
		"Step 1: use search with types=['foaf:Person'] and the author's name to find matching Person entities. "
		"If multiple people are returned, select the most likely match (clarify ambiguity in your answer). "
		"Step 2: use find_by_contributor with the Person @id to retrieve their datasets. "
		"Step 3: for the most relevant datasets, use get_content to read supporting documentation, "
		"and get_relations with predicate='dcat:theme' to understand research themes. "
		"Step 4: summarise the author's research focus and key datasets."
	)


@mcp.prompt()
def explore_dataset(uri: str) -> str:
	"""Deep-dive into a single dataset using the DOO graph.

	Chains doo://context → doo://entity/{uri} → get_relations → get_contributors → get_content.
	Use when a user wants a comprehensive overview of a specific dataset.

	Args:
	    uri: The dataset URI (@id), e.g. "https://catalogue.ceh.ac.uk/id/{uuid}".
	"""
	return (
		f"Provide a comprehensive overview of the dataset at '{uri}'. "
		"Step 1: read doo://context to understand available predicates and types. "
		f"Step 2: read doo://entity/{uri} to get the dataset's core properties. "
		"Step 3: use get_relations to explore: "
		"  - themes (predicate='dcat:theme'), "
		"  - related datasets (predicate='dcterms:isPartOf' or 'dcterms:relation'), "
		"  - supporting documents (predicate='dcterms:references'), "
		"  - incoming citations (predicate='dcterms:isReferencedBy'). "
		"Step 4: use get_contributors to list authors, custodians, and publishers. "
		"Step 5: use get_content on the dataset URI to retrieve its description and lineage text. "
		"Step 6: summarise what the dataset covers, who created it, what it relates to, and its key themes."
	)
