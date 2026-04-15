from haystack import component
from typing import Dict, List, Any, Literal
from haystack_integrations.components.embedders.amazon_bedrock import (
	AmazonBedrockTextEmbedder,
)


@component
class BedrockNodeEmbedder:
	def __init__(
		self,
		model: Literal["amazon.titan-embed-text-v2:0"] = "amazon.titan-embed-text-v2:0",
	):
		self.embedder = AmazonBedrockTextEmbedder(model=model)

	def _prepare_nodes_to_embed(
		self, node_type: str, nodes: List[Dict[str, Any]]
	) -> List[str]:
		return [f"{node_type}: {repr(node)}" for node in nodes]

	def _embed_node(self, node: str):
		return self.embedder.run(text=node)["embedding"]

	def _embed_nodes(
		self, node_type: str, nodes: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		nodes_to_embed = self._prepare_nodes_to_embed(node_type, nodes)
		embeddings = [self._embed_node(node) for node in nodes_to_embed]
		for node, emb in zip(nodes, embeddings):
			node["embedding"] = emb
		return nodes

	@component.output_types(node_embeddings=Dict[str, List[Dict[str, str]]])
	def run(
		self, nodes: Dict[str, List[Dict[str, Any]]]
	) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
		embedded_nodes = {}
		for node_type, node_list in nodes.items():
			embedded_nodes[node_type] = self._embed_nodes(node_type, node_list)
		return {"node_embeddings": embedded_nodes}
