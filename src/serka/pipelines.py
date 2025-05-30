from dataclasses import dataclass
from haystack import Pipeline
from haystack.components.preprocessors import DocumentSplitter
from serka.graph.embedders import OllamaNodeEmbedder
from serka.graph.writers import Neo4jGraphWriter
from serka.graph.extractors import (
	EntityExtractor,
	TextExtractor,
)
from serka.fetchers import EIDCFetcher, LegiloFetcher
from typing import Optional, Callable
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack.components.builders import PromptBuilder
from haystack.components.builders.answer_builder import AnswerBuilder
from haystack_integrations.components.generators.ollama.generator import OllamaGenerator
from haystack.dataclasses import StreamingChunk
from haystack.components.joiners import DocumentJoiner
from serka.prompts import GRAPH_PROMPT, QUERY_TYPE_PROMPT
from serka.graph.readers import Neo4jGraphReader
from serka.graph.embedders import HypotheticalDocumentEmbedder
from haystack.components.routers import ConditionalRouter
from haystack.components.joiners import StringJoiner, AnswerJoiner


@dataclass
class PipelineBuilder:
	ollama_host: str = "localhost"
	ollama_port: int = 11434
	neo4j_host: str = "localhost"
	neo4j_port: int = 7687
	neo4j_user: str = ""
	neo4j_password: str = ""
	legilo_user: str = ""
	legilo_password: str = ""
	embedding_model: str = "nomic-embed-text"
	rag_model: str = "llama3.1"
	chunk_length: int = 150
	chunk_overlap: int = 50

	def _create_embedder(self, hyde: bool = False):
		if hyde:
			return HypotheticalDocumentEmbedder(
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				llm_model=self.rag_model,
				embedding_model=self.embedding_model,
			)
		else:
			return OllamaTextEmbedder(
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				model=self.embedding_model,
			)

	def rag_pipeline(
		self,
		hyde: bool = False,
		streaming_callback: Optional[Callable[[StreamingChunk], None]] = None,
	):
		p = Pipeline()

		p.add_component("query_type_prompt_builder", PromptBuilder(QUERY_TYPE_PROMPT))
		p.add_component(
			"llm_type_classifier",
			OllamaGenerator(
				model="llama3.1",
				generation_kwargs={"num_ctx": 16384, "temperature": 0.0},
				url=f"http://{self.ollama_host}:{self.ollama_port}",
			),
		)
		p.add_component(
			"router",
			ConditionalRouter(
				routes=[
					{
						"condition": "{{'UNRELATED' in replies[0]}}",
						"output": 'I\'m afraid your query: "{{query}}" does not appear to be related to environmental science or the EIDC. Please try asking a different question.',
						"output_name": "unrelated_query",
						"output_type": str,
					},
					{
						"condition": "{{'CODE' in replies[0]}}",
						"output": [
							"Unfortunately I can't generate code. I can try to help you find environmental science data in the EIDC."
						],
						"output_name": "code_query",
						"output_type": str,
					},
					{
						"condition": "{{'UNRELATED' not in replies[0]}}",
						"output": "{{query}}",
						"output_name": "handle_query",
						"output_type": str,
					},
				]
			),
		)
		p.add_component("invalid_joiner", StringJoiner())
		p.add_component("invalid_answer_builder", AnswerBuilder())

		p.add_component(
			"embedder",
			self._create_embedder(hyde=hyde),
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

		p.add_component("answer_joiner", AnswerJoiner())

		p.connect("query_type_prompt_builder", "llm_type_classifier")
		p.connect("llm_type_classifier.replies", "router.replies")
		p.connect("router.unrelated_query", "invalid_joiner")
		p.connect("router.code_query", "invalid_joiner")
		p.connect("invalid_joiner", "invalid_answer_builder")
		p.connect("router.handle_query", "embedder.text")
		p.connect("router.handle_query", "prompt_builder.query")

		p.connect("embedder", "reader")
		p.connect("reader.markdown_nodes", "prompt_builder.markdown_nodes")
		p.connect("prompt_builder", "llm")
		p.connect("llm.replies", "answer_builder")
		p.connect("prompt_builder.prompt", "answer_builder.query")

		p.connect("answer_builder", "answer_joiner")
		p.connect("invalid_answer_builder", "answer_joiner")
		return p

	def build_graph_pipeline(
		self, neo4j_username: str = "neo4j", neo4j_password: str = "password"
	) -> Pipeline:
		p = Pipeline()
		p.add_component("eidc_fetcher", EIDCFetcher())
		p.add_component(
			"legilo_fetcher",
			LegiloFetcher(username=self.legilo_user, password=self.legilo_password),
		)
		p.add_component("ent_extractor", EntityExtractor())
		p.add_component("text_extractor", TextExtractor(["description", "lineage"]))
		p.add_component("joiner", DocumentJoiner())
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

		p.connect("eidc_fetcher", "ent_extractor")
		p.connect("eidc_fetcher", "text_extractor")
		p.connect("eidc_fetcher", "legilo_fetcher")

		p.connect("text_extractor", "joiner")
		p.connect("legilo_fetcher", "joiner")

		p.connect("joiner", "splitter")
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
