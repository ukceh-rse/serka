from typing import Set, List, Union
from pathlib import Path
from haystack import component
from haystack.dataclasses import ByteStream, Document
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


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
					"dataset": dataset.get("title", "unknown_dataset"),
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
