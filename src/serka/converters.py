from typing import Set, List, Union
from pathlib import Path
from haystack import component
from haystack.dataclasses import ByteStream, Document
from haystack.components.converters.utils import get_bytestream_from_source
from trafilatura import bare_extraction
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


@component
class HTMLConverter:
	"""
	Converter for transform generic HTML pages into haystack Documents.
	"""

	@component.output_types(documents=List[Document])
	def run(self, sources: List[ByteStream]):
		"""
		Processes bytestreams and extracts the text content, title, author and
		date from HTML pages using Trafilatura.

		Args:
			sources (List[ByteStream]): List of ByteStream objects containing
			the HTML content.

		Returns:
			dict: A dictionary containing the content extracted from the HTML
			as haystack documents.
		"""
		docs = []
		for source in sources:
			bytesream = get_bytestream_from_source(source)
			result = bare_extraction(
				bytesream.data.decode("utf-8"),
				with_metadata=True,
				output_format="python",
			)
			docs.append(
				Document(
					content=result.text,
					meta={
						"title": result.title,
						"author": result.author,
						"date": result.date,
						"url": result.url,
					},
				)
			)
		return {"documents": docs}


@component
class EIDCConverter:
	def __init__(self, fields: Set[str]):
		self.fields = fields

	def _extract_url(self, identifiers):
		for identifier in identifiers:
			if identifier.startswith("http"):
				return identifier
		return "unknown_url"

	def _extract_fields(self, dataset):
		docs = []
		for field in self.fields:
			if field not in dataset:
				logger.warning("Field {field} not found in dataset. Skipping it.")
				continue
			timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
			d = Document(
				content=dataset[field],
				meta={
					"title": dataset.get("title", "unknown_dataset"),
					"section": field,
					"retrieved": timestamp,
					"url": self._extract_url(dataset.get("resourceIdentifier", [])),
				},
			)
			docs.append(d)
		return docs

	@component.output_types(documents=List[Document])
	def run(self, sources: List[Union[str, Path, ByteStream]]):
		docs = []
		for source in sources:
			try:
				data = source.data.decode("utf-8")
				data = json.loads(data)
				for dataset in data["results"]:
					docs.extend(self._extract_fields(dataset))
			except Exception as e:
				logger.warning(f"Could not read {source}. Skipping it. Error: {e}")
				continue
		return {"documents": docs}


@component
class UnifiedEmbeddingConverter:
	"""
	Converts the content of a document to include metadata the specified metadata fields.
	Also includes the original content as an additional metadata field to ensure it is preserved.
	"""

	def __init__(self, fields: Set[str]):
		self.fields = fields

	@component.output_types(documents=List[Document])
	def run(self, documents: List[Document]):
		for doc in documents:
			doc.meta["content"] = doc.content
			unified_content = "\n".join(
				[
					f"{field}: {doc.meta.get(field)}"
					for field in self.fields
					if doc.meta.get(field)
				]
			)
			if self.fields:
				unified_content += "\ncontent:\n"
			unified_content += f"{doc.content}"
			doc.content = unified_content
		return {"documents": documents}


@component
class LegiloConverter:
	"""
	Converts JSON responses from the Legilo API into haystack Documents.
	"""

	def _extract_supporting_docs(self, data):
		docs = []
		success = data.get("success", False)
		if success:
			for key, value in success.items():
				docs.append(
					Document(
						content=value,
						meta={"title": "Supporting Documentation", "section": key},
					)
				)
		return docs

	@component.output_types(documents=List[Document])
	def run(self, sources: List[Union[str, Path, ByteStream]]):
		docs = []
		for source in sources:
			try:
				data = source.data.decode("utf-8")
				data = json.loads(data)
				docs += self._extract_supporting_docs(data)
			except Exception:
				continue
		return {"documents": docs}
