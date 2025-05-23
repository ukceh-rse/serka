from dataclasses import dataclass
from haystack import Pipeline
from haystack.components.preprocessors import DocumentSplitter
from serka.graph.embedders import OllamaNodeEmbedder
from serka.graph.writers import Neo4jGraphWriter
from serka.graph.extractors import (
	EntityExtractor,
	TextExtractor,
)
from serka.fetchers import EIDCFetcher
from typing import Optional, Callable
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack.components.builders import PromptBuilder
from haystack.components.builders.answer_builder import AnswerBuilder
from haystack_integrations.components.generators.ollama.generator import OllamaGenerator
from haystack.dataclasses import StreamingChunk
from .prompts import GRAPH_PROMPT
from serka.graph.readers import Neo4jGraphReader


@dataclass
class PipelineBuilder:
	ollama_host: str
	ollama_port: int
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
		streaming_callback: Optional[Callable[[StreamingChunk], None]] = None,
	):
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
		p.add_component("prompt_builder", PromptBuilder(GRAPH_PROMPT))
		p.add_component(
			"llm",
			OllamaGenerator(
				model="llama3.1",
				generation_kwargs={"num_ctx": 16384, "temperature": 0.0},
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				streaming_callback=streaming_callback,
			),
		)
		p.add_component("answer_builder", AnswerBuilder())

		p.connect("embedder", "reader")
		p.connect("reader.markdown_nodes", "prompt_builder.markdown_nodes")
		p.connect("prompt_builder", "llm")
		p.connect("llm.replies", "answer_builder.replies")
		p.connect("prompt_builder.prompt", "answer_builder.query")
		return p

	def build_graph_pipeline(
		self, neo4j_username: str = "neo4j", neo4j_password: str = "password"
	) -> Pipeline:
		p = Pipeline()
		p.add_component("fetcher", EIDCFetcher())
		p.add_component("ent_extractor", EntityExtractor())
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

		p.connect("fetcher", "ent_extractor")
		p.connect("fetcher", "text_extractor")

		p.connect("text_extractor", "splitter")
		p.connect("splitter", "doc_emb")
		p.connect("doc_emb", "graph_writer.docs")

		p.connect("ent_extractor", "node_emb")
		p.connect("node_emb", "graph_writer.nodes")
		p.connect("ent_extractor.relationships", "graph_writer.relations")
		return p

	def query_pipeline(self):
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
