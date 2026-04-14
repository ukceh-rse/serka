from app import mcp


@mcp.prompt()
def find_datasets_for_location(location: str) -> str:
	"""Guided workflow for finding EIDC datasets covering a named UK location.

	Chains geocode_location → search with bounding box to resolve a place name into
	geographic coordinates and then retrieve spatially relevant datasets. Use when a user
	asks about datasets for a specific area, region, or site by name rather than coordinates.

	Args:
	    location (str): A UK place name, region, or geographic feature (e.g. "Cairngorms",
	        "River Severn", "Norfolk Broads").
	"""
	return (
		f"Find environmental datasets relevant to '{location}'. "
		"Step 1: use geocode_location to resolve the place name to a bounding box. "
		"Step 2: use search with that bounding box to find relevant datasets. "
		"Step 3: summarise the datasets found, noting their titles, publication dates, and citation counts."
	)


@mcp.prompt()
def explore_author_work(author: str) -> str:
	"""Guided workflow for exploring a researcher's contributions to the EIDC catalogue.

	Chains search (result_type='person') → find_datasets_by_author → get_dataset_documents.
	Because names can be shared, the author is first identified unambiguously via semantic
	search to obtain their ORCID URI before datasets are retrieved. Use when a user wants to
	understand a specific researcher's body of work, research focus, or methodologies.

	Args:
	    author (str): The researcher's name as the user provided it.
	"""
	return (
		f"Explore the published work of '{author}' in the EIDC catalogue. "
		"Step 1: use search with result_type='person' and the author's name as the search term to find matching Person results. "
		"If multiple people are returned, select the most likely based on the user input (but clarify if there were other people with similar names in your answer) "
		"Step 2: extract the uri field from the confirmed Person result and pass it to find_datasets_by_author to retrieve their datasets. "
		"Step 3: for the most relevant datasets, use get_dataset_documents to read supporting documentation. "
		"Step 4: summarise the author's research themes and key datasets."
	)
