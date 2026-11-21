"""Download stage: fetches EIDC metadata and original supporting files into the raw store."""

import logging
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

from serka.fetchers import ConceptHierarchyFetcher, fetch_gemet_broader
from serka.graph.extractors import EntityExtractor
from serka.raw import (
	DEFAULT_SEED,
	DatasetOrder,
	DatasetStatus,
	RawStore,
	build_order,
	extend_order,
)

logger = logging.getLogger(__name__)

EIDC_SEARCH_URL = "https://catalogue.ceh.ac.uk/eidc/documents"
EIDC_RECORD_URL = "https://catalogue.ceh.ac.uk/documents/{id}?format=json"
SUPPORTING_DOCS_URL = "https://data-package.ceh.ac.uk/sd/{id}.zip"
EIDC_PUBLISHED_DATASETS = "state:published AND recordType:Dataset"
SEARCH_PAGE_ROWS = 500
HTTP_TIMEOUT = 60
HTTP_NOT_FOUND = 404
DOWNLOAD_CHUNK_BYTES = 1 << 20


def fetch_metadata(session: requests.Session, dataset_id: str) -> dict[str, Any]:
	"""The dataset's EIDC record as JSON."""
	res: requests.Response = session.get(
		EIDC_RECORD_URL.format(id=dataset_id), timeout=HTTP_TIMEOUT
	)
	res.raise_for_status()
	return res.json()


def fetch_supporting_zip(
	session: requests.Session, dataset_id: str, dest: Path
) -> Path | None:
	"""Streams the dataset's supporting-documents zip to `dest`, or returns None when it has none."""
	url: str = SUPPORTING_DOCS_URL.format(id=dataset_id)
	with session.get(url, stream=True, timeout=HTTP_TIMEOUT) as res:
		if res.status_code == HTTP_NOT_FOUND:
			return None
		res.raise_for_status()
		with dest.open("wb") as out:
			for chunk in res.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
				out.write(chunk)
	return dest


def download_dataset(
	session: requests.Session, store: RawStore, dataset_id: str
) -> DatasetStatus:
	"""Fetches one dataset's metadata and supporting files and stores them as a complete dataset."""
	metadata: dict[str, Any] = fetch_metadata(session, dataset_id)
	store.root.mkdir(parents=True, exist_ok=True)
	with tempfile.TemporaryDirectory(dir=store.root, prefix=".download-") as tmp:
		zip_path: Path | None = fetch_supporting_zip(
			session, dataset_id, Path(tmp) / "sd.zip"
		)
		status: DatasetStatus = store.write_dataset(dataset_id, metadata, zip_path)
	if zip_path and not status.has_supporting_docs:
		logger.warning(
			"Supporting-documents zip for %s has no supporting-documents/ files",
			dataset_id,
		)
	return status


def storing_gemet_lookup(
	session: requests.Session, store: RawStore
) -> Callable[[str], list[dict[str, Any]]]:
	"""A GEMET broader lookup that reads the raw store and fetches and stores what is missing."""

	def broader(uri: str) -> list[dict[str, Any]]:
		if store.gemet_path(uri).exists():
			return store.stored_gemet_broader(uri)
		parents: list[dict[str, Any]] = fetch_gemet_broader(session, uri)
		store.save_gemet_broader(uri, parents)
		return parents

	return broader


def list_published_ids(
	session: requests.Session, url: str = EIDC_SEARCH_URL
) -> list[str]:
	"""Every published EIDC dataset ID, paging through the catalogue search.

	Raises:
		RuntimeError: If the IDs collected do not match the catalogue's `numFound`.
	"""
	ids: dict[str, None] = {}
	page: int = 1
	expected: int | None = None
	while expected is None or len(ids) < expected:
		params: dict[str, Any] = {
			"rows": SEARCH_PAGE_ROWS,
			"page": page,
			"term": EIDC_PUBLISHED_DATASETS,
		}
		res: requests.Response = session.get(url, params=params, timeout=HTTP_TIMEOUT)
		res.raise_for_status()
		body: dict[str, Any] = res.json()
		expected = int(body["numFound"])
		results: list[dict[str, Any]] = body["results"]
		if not results:
			break
		ids.update(dict.fromkeys(r["identifier"] for r in results))
		page += 1
	if len(ids) != expected:
		raise RuntimeError(
			f"EIDC search reported {expected} datasets but returned {len(ids)}"
		)
	logger.info("EIDC: %d published datasets", len(ids))
	return list(ids)


@dataclass
class DownloadRequest:
	"""What to download: the first `n` datasets of the order (all when None)."""

	n: int | None
	head: list[str] = field(default_factory=list)
	seed: int = DEFAULT_SEED
	refresh: bool = False
	reorder: bool = False


@dataclass
class DownloadSummary:
	"""Counts from one download run; `failed` lists dataset IDs that could not be stored."""

	selected: int = 0
	fetched: int = 0
	skipped: int = 0
	failed: list[str] = field(default_factory=list)


def prepare_order(
	session: requests.Session, store: RawStore, request: DownloadRequest
) -> DatasetOrder:
	"""Creates the order on the first run or with `reorder`; otherwise extends the stored one."""
	published: list[str] = list_published_ids(session)
	order: DatasetOrder | None = store.load_order()
	if order is None or request.reorder:
		order = build_order(published, request.head, request.seed)
	else:
		if request.head and request.head != order.head:
			logger.warning(
				"Ignoring the ids file: the raw store already has an order (use --reorder to rebuild it)"
			)
		order = extend_order(order, published)
	store.save_order(order)
	return order


def download_datasets(
	session: requests.Session, store: RawStore, ids: list[str], refresh: bool
) -> DownloadSummary:
	"""Stores each dataset not yet complete (all of them with `refresh`); a failed dataset is logged and skipped."""
	summary: DownloadSummary = DownloadSummary(selected=len(ids))
	for dataset_id in tqdm(ids, desc="Downloading datasets", unit="dataset"):
		if store.is_complete(dataset_id) and not refresh:
			summary.skipped += 1
			continue
		try:
			download_dataset(session, store, dataset_id)
		except (requests.RequestException, zipfile.BadZipFile, ValueError) as e:
			logger.error("Download failed for dataset %s: %s", dataset_id, e)
			summary.failed.append(dataset_id)
			continue
		summary.fetched += 1
	return summary


def store_gemet_hierarchy(
	session: requests.Session, store: RawStore, ids: list[str]
) -> None:
	"""Fetches and stores the GEMET broader concepts that the complete datasets' themes need."""
	records: list[dict[str, Any]] = [
		store.metadata(i) for i in ids if store.is_complete(i)
	]
	extracted: dict[str, Any] = EntityExtractor().run(data=records)
	ConceptHierarchyFetcher(broader=storing_gemet_lookup(session, store)).run(
		nodes=extracted["nodes"], relationships=extracted["relationships"]
	)


def download(
	session: requests.Session, store: RawStore, request: DownloadRequest
) -> DownloadSummary:
	"""Runs the download stage: order, datasets, then GEMET lookups for the selected datasets."""
	order: DatasetOrder = prepare_order(session, store, request)
	ids: list[str] = order.first(request.n)
	summary: DownloadSummary = download_datasets(session, store, ids, request.refresh)
	store_gemet_hierarchy(session, store, ids)
	logger.info(
		"Download: %d selected, %d fetched, %d already stored, %d failed",
		summary.selected,
		summary.fetched,
		summary.skipped,
		len(summary.failed),
	)
	return summary
