from typing import Callable, List, Dict, Any, Tuple
import logging
import requests
from tqdm import tqdm
from haystack import component

logger = logging.getLogger(__name__)


_GEMET_NS = "http://www.eionet.europa.eu/gemet/concept/"
_GEMET_BROADER_URL = "https://www.eionet.europa.eu/gemet/getRelatedConcepts"
_SKOS_BROADER = "http://www.w3.org/2004/02/skos/core#broader"


def fetch_gemet_broader(session: requests.Session, uri: str, url: str = _GEMET_BROADER_URL) -> List[Dict[str, Any]]:
	"""The GEMET API's broader concepts of `uri`.

	Raises:
		requests.HTTPError: If GEMET answers with an HTTP error.
	"""
	res = session.get(url, params={"concept_uri": uri, "relation_uri": _SKOS_BROADER})
	res.raise_for_status()
	return res.json()


@component
class ConceptHierarchyFetcher:
	"""
	Haystack component that adds skos:broader ancestors for GEMET concepts, so a theme
	filter on a general concept can be expanded to the more specific concepts datasets use.
	Args:
		max_depth (int): Maximum number of broader steps to walk up from each concept.
		broader: Returns a concept's broader GEMET concepts (from the raw store, or fetching and storing them).
	"""

	def __init__(self, broader: Callable[[str], List[Dict[str, Any]]], max_depth: int = 6):
		self.max_depth = max_depth
		self._lookup = broader

	@component.output_types(
		nodes=Dict[str, List[Dict[str, Any]]],
		relationships=Dict[str, List[Tuple]],
	)
	def run(
		self, nodes: Dict[str, List[Dict[str, Any]]], relationships: Dict[str, List[Tuple]]
	) -> Dict[str, Any]:
		concepts = {c["uri"]: c for c in nodes.get("Concept", [])}
		broader_rels: set[Tuple] = set()
		frontier = [uri for uri in concepts if uri.startswith(_GEMET_NS)]
		for _ in range(self.max_depth):
			next_frontier = []
			for uri in tqdm(frontier, desc="Fetching GEMET broader concepts", unit="concept"):
				try:
					parents = self._lookup(uri)
				except Exception as e:
					logger.error("GEMET: error fetching broader of %s: %s", uri, e)
					continue
				for parent in parents:
					parent_uri = parent.get("uri")
					if not parent_uri:
						continue
					broader_rels.add((uri, parent_uri))
					if parent_uri not in concepts:
						concepts[parent_uri] = {
							"uri": parent_uri,
							"label": parent.get("preferredLabel", {}).get("string", ""),
							"scheme": "gemet",
						}
						next_frontier.append(parent_uri)
			if not next_frontier:
				break
			frontier = next_frontier

		logger.info("GEMET: %d broader relation(s), %d concept(s) in total", len(broader_rels), len(concepts))
		return {
			"nodes": {**nodes, "Concept": list(concepts.values())},
			"relationships": {**relationships, "BROADER": list(broader_rels)},
		}
