"""Local raw store of EIDC source material: dataset order, metadata, original supporting files,
GEMET lookups and the Markdown that the local Legilo converts supporting files to.

A dataset counts as downloaded only once its `status/<id>.json` exists, which is written last.
"""

import hashlib
import json
import logging
import random
import shutil
import uuid
import zipfile
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

SUPPORTING_DOCS_PREFIX = "supporting-documents/"
DEFAULT_SEED = 20261120


def parse_size(value: str) -> int | None:
	"""A bundle size from the command line: a positive integer, or `all` (None)."""
	if value == "all":
		return None
	size: int = int(value)
	if size <= 0:
		raise ValueError("size must be a positive integer or 'all'")
	return size


def size_name(size: int | None) -> str:
	"""Directory name for a bundle size: the number, or `full`."""
	return "full" if size is None else str(size)


def read_ids_file(path: Path) -> list[str]:
	"""Dataset IDs from a file, one per line; text after `#` is ignored."""
	lines = (
		line.split("#", 1)[0].strip()
		for line in path.read_text(encoding="utf-8").splitlines()
	)
	return [line for line in lines if line]


class DatasetStatus(BaseModel):
	"""Written last when a dataset's metadata and supporting files are fully stored."""

	downloaded: datetime
	has_supporting_docs: bool


class ConversionResult(BaseModel):
	"""Written when Legilo has converted a dataset's supporting files; `errors` maps file name to reason."""

	converted: datetime
	errors: dict[str, str] = {}


class DatasetOrder(BaseModel):
	"""Every dataset ID in ingest order: the ids-file head, then the rest shuffled with `seed`."""

	seed: int
	head: list[str]
	ids: list[str]

	def first(self, n: int | None) -> list[str]:
		"""The first `n` IDs, or all of them when `n` is None."""
		return self.ids if n is None else self.ids[:n]


def build_order(
	published: Iterable[str], head: Sequence[str], seed: int = DEFAULT_SEED
) -> DatasetOrder:
	"""Head IDs first in their given order (duplicates dropped), then every other published ID,
	sorted and shuffled with `seed` so the order depends only on the ID set and the seed."""
	head_ids: list[str] = list(dict.fromkeys(head))
	rest: list[str] = sorted(set(published) - set(head_ids))
	random.Random(seed).shuffle(rest)
	return DatasetOrder(seed=seed, head=head_ids, ids=head_ids + rest)


def extend_order(order: DatasetOrder, published: Iterable[str]) -> DatasetOrder:
	"""Appends published IDs missing from `order`, shuffled with its seed, keeping every existing prefix."""
	new: list[str] = sorted(set(published) - set(order.ids))
	random.Random(order.seed).shuffle(new)
	return order.model_copy(update={"ids": order.ids + new})


def _member_path(name: str) -> PurePosixPath | None:
	"""A zip member's path below `supporting-documents/`, or None for other entries and unsafe paths."""
	if not name.startswith(SUPPORTING_DOCS_PREFIX) or name.endswith("/"):
		return None
	rel: PurePosixPath = PurePosixPath(name[len(SUPPORTING_DOCS_PREFIX) :])
	if rel.is_absolute() or ".." in rel.parts or not rel.parts:
		logger.warning("Skipping unsafe zip entry %s", name)
		return None
	return rel


def extract_supporting_docs(zip_path: Path, dest: Path) -> int:
	"""Extracts the `supporting-documents/` entries of a data-package zip into `dest`.

	Returns:
		The number of files extracted.
	"""
	count: int = 0
	with zipfile.ZipFile(zip_path) as zf:
		for info in zf.infolist():
			rel: PurePosixPath | None = _member_path(info.filename)
			if rel is None:
				continue
			target: Path = dest.joinpath(*rel.parts)
			target.parent.mkdir(parents=True, exist_ok=True)
			with zf.open(info) as src, target.open("wb") as out:
				shutil.copyfileobj(src, out)
			count += 1
	return count


def _write_text_atomic(path: Path, text: str) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	tmp: Path = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex[:8]}")
	tmp.write_text(text, encoding="utf-8")
	tmp.replace(path)


class RawStore:
	"""The raw store directory and its layout (see the staged-eidc-ingestion design)."""

	def __init__(self, root: Path) -> None:
		self.root: Path = root

	@property
	def order_path(self) -> Path:
		return self.root / "order.json"

	@property
	def supporting_docs_root(self) -> Path:
		return self.root / "supporting-docs"

	def metadata_path(self, dataset_id: str) -> Path:
		return self.root / "metadata" / f"{dataset_id}.json"

	def supporting_dir(self, dataset_id: str) -> Path:
		return self.supporting_docs_root / dataset_id

	def status_path(self, dataset_id: str) -> Path:
		return self.root / "status" / f"{dataset_id}.json"

	def markdown_dir(self, dataset_id: str) -> Path:
		return self.root / "markdown" / dataset_id

	def conversion_path(self, dataset_id: str) -> Path:
		return self.markdown_dir(dataset_id) / "_result.json"

	def gemet_path(self, uri: str) -> Path:
		return self.root / "gemet" / f"{hashlib.sha1(uri.encode()).hexdigest()}.json"

	def load_order(self) -> DatasetOrder | None:
		"""The stored order, or None before the first download."""
		if not self.order_path.exists():
			return None
		return DatasetOrder.model_validate_json(
			self.order_path.read_text(encoding="utf-8")
		)

	def save_order(self, order: DatasetOrder) -> None:
		_write_text_atomic(self.order_path, order.model_dump_json(indent=1))

	def is_complete(self, dataset_id: str) -> bool:
		return self.status_path(dataset_id).exists()

	def status(self, dataset_id: str) -> DatasetStatus:
		return DatasetStatus.model_validate_json(
			self.status_path(dataset_id).read_text(encoding="utf-8")
		)

	def metadata(self, dataset_id: str) -> dict[str, Any]:
		return json.loads(self.metadata_path(dataset_id).read_text(encoding="utf-8"))

	def write_dataset(
		self, dataset_id: str, metadata: dict[str, Any], zip_path: Path | None
	) -> DatasetStatus:
		"""Stores a dataset's metadata and the supporting files from its data-package zip, then marks it
		complete. Until the status file is written the dataset counts as not downloaded, and a failure
		leaves no temporary files behind."""
		self.status_path(dataset_id).unlink(missing_ok=True)
		tmp: Path = (
			self.supporting_docs_root / f".{dataset_id}.tmp-{uuid.uuid4().hex[:8]}"
		)
		tmp.mkdir(parents=True)
		try:
			count: int = extract_supporting_docs(zip_path, tmp) if zip_path else 0
			shutil.rmtree(self.supporting_dir(dataset_id), ignore_errors=True)
			tmp.rename(self.supporting_dir(dataset_id))
		finally:
			shutil.rmtree(tmp, ignore_errors=True)
		_write_text_atomic(self.metadata_path(dataset_id), json.dumps(metadata))
		status: DatasetStatus = DatasetStatus(
			downloaded=datetime.now(timezone.utc), has_supporting_docs=count > 0
		)
		_write_text_atomic(self.status_path(dataset_id), status.model_dump_json())
		return status

	def save_gemet_broader(self, uri: str, broader: list[dict[str, Any]]) -> None:
		_write_text_atomic(self.gemet_path(uri), json.dumps(broader))

	def stored_gemet_broader(self, uri: str) -> list[dict[str, Any]]:
		"""The stored GEMET broader concepts of `uri`; a missing lookup gives a warning and none."""
		path: Path = self.gemet_path(uri)
		if not path.exists():
			logger.warning("GEMET broader concepts of %s are not in the raw store", uri)
			return []
		return json.loads(path.read_text(encoding="utf-8"))

	def save_conversion(self, dataset_id: str, result: ConversionResult) -> None:
		_write_text_atomic(
			self.conversion_path(dataset_id), result.model_dump_json(indent=1)
		)

	def conversion(self, dataset_id: str) -> ConversionResult | None:
		"""The stored conversion result, or None when the dataset has not been converted yet."""
		path: Path = self.conversion_path(dataset_id)
		if not path.exists():
			return None
		return ConversionResult.model_validate_json(path.read_text(encoding="utf-8"))
