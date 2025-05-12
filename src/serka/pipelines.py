from dataclasses import dataclass
from haystack import Pipeline
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack.components.preprocessors import DocumentSplitter
from serka.converters import (
	EIDCConverter,
	HTMLConverter,
	UnifiedEmbeddingConverter,
	LegiloConverter,
)
from serka.graph.embedders import OllamaNodeEmbedder
from serka.graph.writers import Neo4jGraphWriter
from serka.graph.extractors import (
	AuthorExtractor,
	OrganisationExtractor,
	DatasetExtractor,
	TextExtractor,
	RelationshipExtractor,
)
from serka.graph.joiners import NodeJoiner
from serka.fetchers import EIDCFetcher
from typing import Dict, List, Optional, Callable
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack.components.writers import DocumentWriter
from haystack.components.fetchers import LinkContentFetcher
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack_integrations.components.retrievers.chroma import ChromaEmbeddingRetriever
from haystack.components.builders import PromptBuilder
from haystack.components.builders.answer_builder import AnswerBuilder
from haystack_integrations.components.generators.ollama.generator import OllamaGenerator
from haystack.dataclasses import StreamingChunk
from .prompts import RAG_PROMPT
from serka.graph.readers import Neo4jGraphReader


@dataclass
class PipelineBuilder:
	ollama_host: str
	ollama_port: int
	chroma_host: str
	chroma_port: int
	neo4j_host: str
	neo4j_port: int
	neo4j_user: str
	neo4j_password: str
	embedding_model: str
	rag_model: str
	chunk_length: int
	chunk_overlap: int

	def rag_pipeline(
		self,
		collection: str,
		streaming_callback: Optional[Callable[[StreamingChunk], None]] = None,
	) -> Pipeline:
		p = self.query_pipeline(collection, top_n=15)
		prompt_builder = PromptBuilder(RAG_PROMPT)
		llm = OllamaGenerator(
			model=self.rag_model,
			generation_kwargs={"num_ctx": 16384, "temperature": 0.0},
			url=f"http://{self.ollama_host}:{self.ollama_port}",
			streaming_callback=streaming_callback,
		)
		answer_builder = AnswerBuilder()

		p.add_component("prompt_builder", prompt_builder)
		p.add_component("llm", llm)
		p.add_component("answer_builder", answer_builder)

		p.connect("retriever.documents", "prompt_builder.documents")
		p.connect("retriever.documents", "answer_builder.documents")
		p.connect("prompt_builder", "llm")
		p.connect("llm.replies", "answer_builder.replies")
		p.connect("prompt_builder.prompt", "answer_builder.query")

		return p

	def query_pipeline(self, collection: str, top_n: int = 5) -> Pipeline:
		doc_store = ChromaDocumentStore(
			host=self.chroma_host,
			port=self.chroma_port,
			collection_name=collection,
		)
		p = Pipeline()

		p.add_component(
			"embedder",
			OllamaTextEmbedder(
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				model=self.embedding_model,
			),
		)
		p.add_component("retriever", ChromaEmbeddingRetriever(doc_store, top_k=top_n))

		p.connect("embedder.embedding", "retriever.query_embedding")

		return p

	def scraping_pipeline(
		self,
		collection,
		type,
		unified_metadata: List[str] = {},
		metadata: Dict[str, str] = {},
	) -> Pipeline:
		p = self.conversion_pipeline(collection, type, unified_metadata, metadata)
		p.add_component("fetcher", LinkContentFetcher(timeout=10))
		p.connect("fetcher.streams", "converter.sources")
		return p

	def conversion_pipeline(
		self,
		collection: str,
		type: str,
		unified_metadata: List[str] = {},
		metadata: Dict[str, str] = {},
	) -> Pipeline:
		p = self.insertion_pipeline(collection, unified_metadata)
		p.add_component("converter", self._create_converter(type, metadata))
		p.connect("converter.documents", "splitter.documents")
		return p

	def _create_converter(self, source_type: str, metadata: Dict[str, str]):
		if source_type == "eidc":
			return EIDCConverter({"description", "lineage"})
		if source_type == "legilo":
			return LegiloConverter(metadata)
		if source_type == "html":
			return HTMLConverter()
		raise ValueError(f"Unknown converter type: {source_type}")

	def eidc_graph_pipeline(
		self, neo4j_username: str = "neo4j", neo4j_password: str = "password"
	) -> Pipeline:
		p = Pipeline()
		p.add_component("fetcher", EIDCFetcher())
		p.add_component("author_extractor", AuthorExtractor())
		p.add_component("orgs_extractor", OrganisationExtractor())
		p.add_component("dataset_extractor", DatasetExtractor())
		p.add_component("text_extractor", TextExtractor(["description", "lineage"]))
		p.add_component(
			"splitter",
			DocumentSplitter(split_by="word", split_length=150, split_overlap=50),
		)
		p.add_component(
			"doc_emb",
			OllamaDocumentEmbedder(
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				meta_fields_to_embed=["title", "field"],
			),
		)
		p.add_component("joiner", NodeJoiner())
		p.add_component("rel_extractor", RelationshipExtractor())
		p.add_component(
			"node_emb",
			OllamaNodeEmbedder(url=f"http://{self.ollama_host}:{self.ollama_port}"),
		)
		p.add_component(
			"graph_writer",
			Neo4jGraphWriter(
				host=self.neo4j_host,
				port=self.neo4j_port,
				username=neo4j_username,
				password=neo4j_password,
			),
		)

		p.connect("fetcher", "author_extractor")
		p.connect("fetcher", "orgs_extractor")
		p.connect("fetcher", "dataset_extractor")
		p.connect("fetcher", "rel_extractor")
		p.connect("fetcher", "text_extractor")

		p.connect("author_extractor", "joiner.authors")
		p.connect("orgs_extractor", "joiner.orgs")
		p.connect("dataset_extractor", "joiner.datasets")

		p.connect("text_extractor", "splitter")
		p.connect("splitter", "doc_emb")
		p.connect("doc_emb", "graph_writer.docs")

		p.connect("joiner", "node_emb")
		p.connect("node_emb", "graph_writer.nodes")
		p.connect("rel_extractor", "graph_writer.relations")
		return p

	def eidc_graph_query_pipeline(self):
		p = Pipeline()
		p.add_component(
			"embedder",
			OllamaTextEmbedder(
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				model=self.embedding_model,
			),
		)
		p.add_component(
			"reader",
			Neo4jGraphReader(
				url=f"bolt://{self.neo4j_host}:{self.neo4j_port}",
				username=self.neo4j_user,
				password=self.neo4j_password,
			),
		)
		p.connect("embedder", "reader")
		return p

	def insertion_pipeline(
		self, collection: str, unified_metadata: List[str] = {}
	) -> Pipeline:
		p = Pipeline()
		doc_store = ChromaDocumentStore(
			host=self.chroma_host,
			port=self.chroma_port,
			collection_name=collection,
		)

		p.add_component(
			"splitter",
			DocumentSplitter(
				split_by="word",
				split_length=self.chunk_length,
				split_overlap=self.chunk_overlap,
			),
		)
		p.add_component("unifier", UnifiedEmbeddingConverter(unified_metadata))
		p.add_component(
			"embedder",
			OllamaDocumentEmbedder(
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				model=self.embedding_model,
			),
		)
		p.add_component("writer", DocumentWriter(doc_store))

		p.connect("splitter.documents", "unifier.documents")
		p.connect("unifier.documents", "embedder.documents")
		p.connect("embedder.documents", "writer.documents")

		return p
