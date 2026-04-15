from dataclasses import dataclass
from haystack import Pipeline
from haystack.components.preprocessors import DocumentSplitter
from serka.graph.embedders import BedrockNodeEmbedder
from serka.graph.writers import Neo4jGraphWriter
from serka.graph.extractors import EntityExtractor, TextExtractor
from serka.fetchers import EIDCFetcher, LegiloFetcher
from typing import Optional, Callable
from haystack_integrations.components.embedders.amazon_bedrock import (
	AmazonBedrockDocumentEmbedder,
	AmazonBedrockTextEmbedder,
)
from haystack_integrations.components.generators.amazon_bedrock import (
	AmazonBedrockGenerator,
	AmazonBedrockChatGenerator,
)
from haystack.dataclasses import StreamingChunk
from haystack.components.joiners import DocumentJoiner
from serka.graph.readers import Neo4jGraphReader
from haystack_integrations.tools.mcp import MCPToolset, StreamableHttpServerInfo
from haystack.components.agents import Agent


@dataclass
class PipelineBuilder:
	models_embedding: str
	models_llm: str
	neo4j_host: str
	neo4j_port: int
	neo4j_user: str
	neo4j_password: str
	mcp_host: str
	mcp_port: int
	legilo_user: str
	legilo_password: str
	chunk_length: int
	chunk_overlap: int

	def _create_text_embedder(self):
		return AmazonBedrockTextEmbedder(model=self.models_embedding)

	def _create_node_embedder(self):
		return BedrockNodeEmbedder(model=self.models_embedding)

	def _create_document_embedder(self):
		return AmazonBedrockDocumentEmbedder(model=self.models_embedding)

	def _create_llm_generator(
		self, streaming_callback: Optional[Callable[[StreamingChunk], None]] = None
	):
		return AmazonBedrockGenerator(
			model=self.models_llm,
			streaming_callback=streaming_callback,
			max_length=500,
		)

	def agent(self) -> Agent:
		server_info = StreamableHttpServerInfo(
			url=f"http://{self.mcp_host}:{self.mcp_port}/mcp"
		)
		toolset = MCPToolset(server_info=server_info)
		generator = AmazonBedrockChatGenerator(model=self.models_llm)
		return Agent(chat_generator=generator, tools=toolset, exit_conditions=["text"])

	def build_graph_pipeline(self) -> Pipeline:
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
		p.add_component("doc_emb", self._create_document_embedder())
		p.add_component("node_emb", self._create_node_embedder())
		p.add_component(
			"graph_writer",
			Neo4jGraphWriter(
				host=self.neo4j_host,
				port=self.neo4j_port,
				username=self.neo4j_user,
				password=self.neo4j_password,
			),
		)

		p.connect("eidc_fetcher", "ent_extractor")
		p.connect("eidc_fetcher", "text_extractor")
		p.connect("eidc_fetcher", "legilo_fetcher")

		p.connect("text_extractor.documents", "joiner.documents")
		p.connect("legilo_fetcher.documents", "joiner.documents")

		p.connect("joiner", "splitter")
		p.connect("splitter", "doc_emb")
		p.connect("doc_emb", "graph_writer.docs")

		p.connect("ent_extractor", "node_emb")
		p.connect("node_emb", "graph_writer.nodes")
		p.connect("ent_extractor.relationships", "graph_writer.relations")
		return p

	def query_pipeline(self) -> Pipeline:
		p = Pipeline()
		p.add_component("embedder", self._create_text_embedder())
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
