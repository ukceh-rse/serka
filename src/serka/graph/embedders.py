from haystack import component
from typing import Dict, List, Any
from ollama import Client
from tqdm import tqdm
from haystack import Pipeline, Document
from numpy import array, mean
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.generators.ollama.generator import OllamaGenerator
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from serka.prompts import HYDE_PROMPT_TEMPLATE, HYDE_SYSTEM_PROMPT


@component
class OllamaNodeEmbedder:
	"""
	A class to embed nodes using the Ollama API. The class uses the Ollama API
	to embed nodes based on their type and their content.
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


@component
class HypotheticalDocumentEmbedder:
	"""
	A class to generate hypothetical documents and embed them using the Ollama API.
	"""

	def __init__(
		self,
		llm_model: str = "llama3.1",
		embedding_model: str = "nomic-embed-text",
		url: str = "http://localhost:11434",
		n: int = 5,
	):
		self.llm_model = llm_model
		self.embedding_model = embedding_model
		self.url = url
		self.n = 5
		self.pipeline = Pipeline()
		self.pipeline.add_component(
			name="prompt_builder", instance=PromptBuilder(template=HYDE_PROMPT_TEMPLATE)
		)
		self.pipeline.add_component(
			"llm",
			OllamaGenerator(
				model="llama3.1",
				url=url,
				system_prompt=HYDE_SYSTEM_PROMPT,
				generation_kwargs={"temperature": 0.5, "n": n, "num_predict": 150},
			),
		)
		self.pipeline.connect("prompt_builder", "llm")

	@component.output_types(hypothetical_embedding=List[float])
	def run(self, text: str) -> Dict[str, List[float]]:
		# Here a loop is used to generate multiple hypothetical documents.
		# Ideally this should be done as a single batch request to the LLM,
		# unfortunately ollama generator does not seem to support multiple
		# responses in a single request (openAI generator suppoprts this with
		# `n` parameter).
		hypothetical_docs = []
		for i in tqdm(range(self.n), desc="Generating hypothetical documents"):
			response = self.pipeline.run(data={"prompt_builder": {"query": text}})
			hypothetical_docs.append(Document(response["llm"]["replies"][0]))

		embedder = OllamaDocumentEmbedder(url=self.url, model=self.embedding_model)
		result = embedder.run(hypothetical_docs)

		stacked_embeddings = array([doc.embedding for doc in result["documents"]])
		avg_embedding = mean(stacked_embeddings, axis=0)
		hyde_vector = avg_embedding.reshape((1, len(avg_embedding)))
		return {"hypothetical_embedding": hyde_vector[0].tolist()}
