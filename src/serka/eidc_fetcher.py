from haystack import Pipeline
from haystack.components.fetchers import LinkContentFetcher
from haystack.components.converters import JSONConverter
from haystack.components.preprocessors import DocumentSplitter
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack.components.writers import DocumentWriter
from typing import List, Dict, Any, Set


class EIDCPipeline:
	def __init__(
		self,
		content_field: str = "description",
		meta_fields: Set[str] = {"identifier", "title"},
		embedding_model: str = "nomic-embed-text",
	) -> None:
		self.fetcher = LinkContentFetcher()
		self.converter = JSONConverter(
			jq_schema=".results[]",
			content_key=content_field,
			extra_meta_fields=meta_fields,
		)
		self.splitter = DocumentSplitter(
			split_by="word", split_length=150, split_overlap=50
		)
		self.embedder = OllamaDocumentEmbedder(model=embedding_model)
		self.doc_store = ChromaDocumentStore(host="localhost", port="8001")
		self.writer = DocumentWriter(document_store=self.doc_store)
		self.pipeline = self._create_pipeline()

	def _create_pipeline(self) -> Pipeline:
		pipeline = Pipeline()
		pipeline.add_component(instance=self.fetcher, name="fetcher")
		pipeline.add_component(instance=self.converter, name="converter")
		pipeline.add_component(instance=self.splitter, name="splitter")
		pipeline.add_component(instance=self.embedder, name="embedder")
		pipeline.add_component(instance=self.writer, name="writer")

		pipeline.connect("fetcher.streams", "converter.sources")
		pipeline.connect("converter.documents", "splitter.documents")
		pipeline.connect("splitter.documents", "embedder.documents")
		pipeline.connect("embedder.documents", "writer.documents")

		return pipeline

	def process(self, urls: List[str]) -> Dict[str, Any]:
		return self.pipeline.run(data={"fetcher": {"urls": urls}})


if __name__ == "__main__":
	pipeline = EIDCPipeline()
	result = pipeline.process(urls=["https://catalogue.ceh.ac.uk/eidc/documents"])
