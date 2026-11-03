import logging
from haystack import component, Document
from typing import Dict, List, Any, Literal
from tqdm import tqdm
from haystack_integrations.components.embedders.amazon_bedrock import (
	AmazonBedrockDocumentEmbedder,
	AmazonBedrockTextEmbedder,
)
import serka.cache as cache

logger = logging.getLogger(__name__)


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

	def _embed_node(self, content: str) -> List[float]:
		cached = cache.get_embedding(content)
		if cached is not None:
			return cached
		embedding = self.embedder.run(text=content)["embedding"]
		cache.save_embedding(content, embedding)
		return embedding

	def _embed_nodes(
		self, node_type: str, nodes: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		result = []
		contents = self._prepare_nodes_to_embed(node_type, nodes)
		for node, content in tqdm(
			zip(nodes, contents),
			desc=f"Embedding {node_type} nodes",
			unit="node",
			total=len(nodes),
		):
			try:
				result.append({**node, "embedding": self._embed_node(content)})
			except Exception as e:
				logger.error(
					"Embedding failed for %s node %s: %s",
					node_type,
					node.get("uri", node.get("name", "?")),
					e,
					exc_info=True,
				)
		return result

	@component.output_types(node_embeddings=Dict[str, List[Dict[str, str]]])
	def run(
		self, nodes: Dict[str, List[Dict[str, Any]]]
	) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
		embedded_nodes = {}
		for node_type, node_list in nodes.items():
			if node_type == "Document":
				embedded_nodes[node_type] = node_list
			else:
				embedded_nodes[node_type] = self._embed_nodes(node_type, node_list)
		return {"node_embeddings": embedded_nodes}


@component
class CachedDocumentEmbedder:
	def __init__(self, model: str = "amazon.titan-embed-text-v2:0", max_chars: int = 30_000, batch_size: int = 100):
		self.embedder = AmazonBedrockDocumentEmbedder(model=model, progress_bar=False)
		self.max_chars = max_chars
		self.batch_size = batch_size

	def _embed(self, docs: List[Document]) -> List[Document | None]:
		"""Embed a batch; if it fails, retry one by one so a single bad document only drops itself."""
		try:
			return self.embedder.run(documents=docs)["documents"]
		except Exception as e:
			if len(docs) == 1:
				logger.error(
					"Document embedding failed: %s | uri=%s | file=%s",
					e,
					docs[0].meta.get("uri", "?"),
					docs[0].meta.get("filename", ""),
				)
				return [None]
			return [self._embed([d])[0] for d in docs]

	@component.output_types(documents=List[Document], meta=Dict[str, Any])
	def run(self, documents: List[Document]) -> Dict[str, Any]:
		result: list[Document | None] = [None] * len(documents)
		to_embed: list[tuple[int, Document]] = []

		for i, doc in tqdm(enumerate(documents), total=len(documents), desc="Loading cached embeddings", unit="doc"):
			if not doc.content:
				result[i] = doc
				continue
			if len(doc.content) > self.max_chars:
				logger.warning(
					"Skipping document: %d chars exceeds limit of %d. "
					"uri=%s | title=%s | file=%s | preview=%r",
					len(doc.content),
					self.max_chars,
					doc.meta.get("uri", "?"),
					doc.meta.get("title", "?"),
					doc.meta.get("filename", ""),
					doc.content[:300],
				)
				continue
			cached = cache.get_embedding(doc.content)
			if cached is not None:
				result[i] = Document(content=doc.content, meta=doc.meta, embedding=cached)
			else:
				to_embed.append((i, doc))

		batches = [to_embed[s : s + self.batch_size] for s in range(0, len(to_embed), self.batch_size)]
		with tqdm(total=len(to_embed), desc="Creating embeddings", unit="doc") as progress:
			for batch in batches:
				indices, docs = zip(*batch)
				for i, embedded_doc in zip(indices, self._embed(list(docs))):
					if embedded_doc is not None and embedded_doc.embedding and embedded_doc.content:
						cache.save_embedding(embedded_doc.content, embedded_doc.embedding)
						result[i] = embedded_doc
				progress.update(len(batch))

		return {"documents": [d for d in result if d is not None], "meta": {}}
