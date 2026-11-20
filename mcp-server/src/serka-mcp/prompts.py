from app import mcp


@mcp.prompt()
def find_datasets_for_location(location: str) -> str:
	"""Find EIDC datasets covering a named UK location.

	Chains geocode_location → search with bounding_box → read. Use when a user asks about
	datasets for a specific area by name.

	Args:
	    location: A UK place name (e.g. "Cairngorms", "River Severn", "Norfolk Broads").
	"""
	return (
		f"Find environmental datasets relevant to '{location}'. "
		"Step 1: use geocode_location to resolve the place name to a bounding_box. "
		"Step 2: use search with that bounding_box and type='dataset' to find relevant datasets. "
		"Step 3: read the most relevant datasets to learn their themes and contributors. "
		"Step 4: summarise the datasets, their themes, and any notable contributors."
	)


@mcp.prompt()
def explore_author_work(author: str) -> str:
	"""Explore a researcher's contributions to the EIDC catalogue.

	Chains search (type='person') → search (linked) → read. Use when a user wants to
	understand a researcher's body of work.

	Args:
	    author: The researcher's name.
	"""
	return (
		f"Explore the published work of '{author}' in the EIDC catalogue. "
		"Step 1: use search with type='person' and the author's name to find matching people. "
		"If several people are returned, select the most likely match (clarify ambiguity in your answer). "
		"Step 2: use search with linked=<the person's concept id> and type='dataset' (with a query or "
		"sort_by='published') to find the datasets that link them. "
		"Step 3: read the most relevant datasets, and their supporting documents, to see the person's "
		"role on each and the research themes. "
		"Step 4: summarise the author's research focus and key datasets."
	)


@mcp.prompt()
def explore_dataset(id: str) -> str:
	"""Deep-dive into a single dataset by following the links in its concept file.

	Chains read → read on linked concepts → search. Use when a user wants a comprehensive
	overview of a specific dataset.

	Args:
	    id: The dataset's concept id, e.g. "datasets/{eidc-id}".
	"""
	return (
		f"Provide a comprehensive overview of the dataset '{id}'. "
		"Step 1: read the dataset to get its description, lineage, contributors, themes, related datasets, "
		"funding, supporting documents and citing publications. "
		"Step 2: read the linked concepts that matter: supporting documents for methods, related datasets, "
		"grants and contributors. Read 'ontology/index' if a role or relation needs explaining. "
		"Step 3: search with linked=<the dataset id> to find concepts that link back to it, such as "
		"datasets that are part of it. "
		"Step 4: summarise what the dataset covers, who created it, what it relates to, and its key themes."
	)
