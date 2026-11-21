"""Build stage: turns the first N datasets of the raw store into an OKF bundle in its own directory.

Needs no EIDC, data-package or GEMET access; supporting files not yet converted go to the local Legilo.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from haystack import Document

from serka.fetchers import ConceptHierarchyFetcher
from serka.graph.extractors import EntityExtractor
from serka.legilo import MARKDOWN_SUFFIX, ConversionSummary, LegiloConverter
from serka.okf.concepts import Concept, build_concepts
from serka.okf.writer import write_bundle
from serka.raw import DatasetOrder, RawStore

logger = logging.getLogger(__name__)

SUPPORTING_DOC_FIELD = "SUPPORTING_DOC"


@dataclass
class BuildSummary:
	"""What one build wrote: concept counts by type and the conversion run's counts."""

	bundle_dir: Path
	concepts: dict[str, int] = field(default_factory=dict)
	conversion: ConversionSummary = field(default_factory=ConversionSummary)


def select_datasets(store: RawStore, size: int | None) -> list[str]:
	"""The first `size` dataset IDs of the order (all when None), every one of them downloaded.

	Raises:
		ValueError: If the raw store has no order, or fewer complete datasets than requested.
	"""
	order: DatasetOrder | None = store.load_order()
	if order is None:
		raise ValueError(f"No dataset order in {store.root}; run scripts/download.py first")
	ids: list[str] = order.first(size)
	complete: int = sum(store.is_complete(i) for i in ids)
	if (size is not None and len(ids) < size) or complete < len(ids):
		wanted: str = "all" if size is None else str(size)
		raise ValueError(
			f"Requested {wanted} datasets but only {complete} of the first {len(ids)} are downloaded; "
			"run scripts/download.py first"
		)
	return ids


def stored_documents(store: RawStore, records: list[dict[str, Any]]) -> list[Document]:
	"""One Document per converted supporting file, holding Legilo's Markdown in full."""
	docs: list[Document] = []
	for record in records:
		md_dir: Path = store.markdown_dir(record["id"])
		for path in sorted(md_dir.glob(f"*{MARKDOWN_SUFFIX}")):
			meta: dict[str, Any] = {
				"title": record.get("title", ""),
				"field": SUPPORTING_DOC_FIELD,
				"uri": record.get("uri", ""),
				"filename": path.name.removesuffix(MARKDOWN_SUFFIX),
			}
			docs.append(Document(content=path.read_text(encoding="utf-8"), meta=meta))
	return docs


def build_bundle(
	store: RawStore, size: int | None, out_dir: Path, converter: LegiloConverter, refresh: bool = False
) -> BuildSummary:
	"""Converts what is still unconverted, then writes the bundle of the first `size` datasets to `out_dir`,
	replacing only that directory."""
	ids: list[str] = select_datasets(store, size)
	conversion: ConversionSummary = converter.convert_all(store, ids, refresh)
	records: list[dict[str, Any]] = [store.metadata(i) for i in ids]
	extracted: dict[str, Any] = EntityExtractor().run(data=records)
	hierarchy: dict[str, Any] = ConceptHierarchyFetcher(broader=store.stored_gemet_broader).run(
		nodes=extracted["nodes"], relationships=extracted["relationships"]
	)
	concepts: list[Concept] = build_concepts(
		records, hierarchy["nodes"], hierarchy["relationships"], stored_documents(store, records)
	)
	write_bundle(out_dir, concepts)
	counts: dict[str, int] = dict(Counter(c.meta["type"] for c in concepts))
	logger.info("OKF bundle of %d datasets written to %s: %s", len(ids), out_dir, counts)
	return BuildSummary(bundle_dir=out_dir.resolve(), concepts=counts, conversion=conversion)
