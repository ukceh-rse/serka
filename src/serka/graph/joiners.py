from haystack import component
from typing import Dict, List, Any


@component
class NodeJoiner:
	@component.output_types(nodes=Dict[str, List[Dict[str, str]]])
	def run(
		self,
		authors: List[Dict[str, Any]],
		orgs: List[Dict[str, Any]],
		datasets: List[Dict[str, Any]],
	) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
		return {"nodes": {"Person": authors, "Organisation": orgs, "Dataset": datasets}}
