from haystack import component
from typing import Dict, List, Any
from ollama import Client
from tqdm import tqdm


@component
class OllamaNodeEmbedder:
	"""
	A class to embed nodes using the Ollama API.
	"""

	def __init__(
		self,
		model: str = "nomic-embed-text",
		url: str = "http://localhost:11434",
		batch_size: int = 32,
	):
		"""
		Initializes the OllamaNodeEmbedder with the specified model and URL.

		:param model: The name of the model to use for embedding.
		:param url: The URL of the Ollama server.
		:param timeout: The timeout for requests to the server.
		"""
		self.model = model
		self.url = url
		self.batch_size = batch_size
		self._client = Client(host=self.url)

	def _prepare_nodes_to_embed(
		self, node_type: str, nodes: List[Dict[str, Any]]
	) -> List[str]:
		nodes_to_embed = []
		for node in nodes:
			nodes_to_embed.append(f"{node_type}: {repr(node)}")
		return nodes_to_embed

	def _embed_batch(self, nodes_to_embed: List[str]):
		all_embeddings = []
		for i in tqdm(
			range(0, len(nodes_to_embed), self.batch_size),
			desc="Calculating embeddings",
		):
			batch = nodes_to_embed[i : i + self.batch_size]
			result = self._client.embed(model=self.model, input=batch)
			all_embeddings.extend(result["embeddings"])
		return all_embeddings

	def _embed_nodes(
		self, node_type: str, nodes: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		nodes_to_embed = self._prepare_nodes_to_embed(node_type, nodes)
		embeddings = self._embed_batch(nodes_to_embed)
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
