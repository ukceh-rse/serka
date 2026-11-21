"""Converts supporting files in the raw store to Markdown with the local Legilo service
(`docker compose --profile ingest up -d legilo`) and caches the result in the raw store."""

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

from serka.raw import ConversionResult, RawStore

logger = logging.getLogger(__name__)

REACHABILITY_TIMEOUT = timedelta(seconds=5)
MARKDOWN_SUFFIX = ".md"


@dataclass
class ConversionSummary:
	"""Counts from one conversion run; `failed` lists datasets Legilo could not convert at all."""

	converted: int = 0
	cached: int = 0
	file_errors: int = 0
	failed: list[str] = field(default_factory=list)


class LegiloConverter:
	"""Client for the local Legilo `/{id}/documents` endpoint.

	Args:
		url: Base URL of the local Legilo service.
		timeout: Longest wait for one dataset's conversion.
	"""

	def __init__(
		self, url: str, timeout: timedelta, session: requests.Session | None = None
	) -> None:
		self.url: str = url.rstrip("/")
		self.timeout: timedelta = timeout
		# Deliberately not the cached HTTP session: the raw store's markdown/ is the cache.
		self.session: requests.Session = session or requests.Session()

	def check_reachable(self) -> None:
		"""Raises ConnectionError, naming the URL, when Legilo does not answer."""
		try:
			res: requests.Response = self.session.get(
				f"{self.url}/openapi.json", timeout=REACHABILITY_TIMEOUT.total_seconds()
			)
			res.raise_for_status()
		except requests.RequestException as err:
			raise ConnectionError(
				f"Local Legilo is not reachable at {self.url} (LEGILO_URL); "
				"start it with `docker compose --profile ingest up -d legilo`"
			) from err

	def convert(self, store: RawStore, dataset_id: str) -> ConversionResult | None:
		"""Converts one dataset's supporting files and stores the Markdown and per-file errors.

		Returns:
			The stored result, or None when Legilo failed for the whole dataset (nothing is stored,
			so a later run tries again).
		"""
		_warn_duplicate_names(store.supporting_dir(dataset_id), dataset_id)
		try:
			res: requests.Response = self.session.get(
				f"{self.url}/{dataset_id}/documents",
				timeout=self.timeout.total_seconds(),
			)
			res.raise_for_status()
			body: dict[str, Any] = res.json()
		except (requests.RequestException, ValueError) as err:
			logger.error("Legilo failed for dataset %s: %s", dataset_id, err)
			return None
		md_dir: Path = store.markdown_dir(dataset_id)
		md_dir.mkdir(parents=True, exist_ok=True)
		for name, markdown in body.get("success", {}).items():
			(md_dir / f"{name}{MARKDOWN_SUFFIX}").write_text(markdown, encoding="utf-8")
		errors: dict[str, str] = {
			k: v.get("description", "") for k, v in body.get("errors", {}).items()
		}
		result: ConversionResult = ConversionResult(
			converted=datetime.now(timezone.utc), errors=errors
		)
		store.save_conversion(dataset_id, result)
		return result

	def convert_all(
		self, store: RawStore, ids: list[str], refresh: bool = False
	) -> ConversionSummary:
		"""Converts every dataset in `ids` that has supporting files and no stored result (all of them
		with `refresh`). Checks Legilo is reachable first, but only when a conversion is needed."""
		summary: ConversionSummary = ConversionSummary()
		pending: list[str] = []
		for dataset_id in ids:
			if not store.status(dataset_id).has_supporting_docs:
				continue
			if store.conversion(dataset_id) is not None and not refresh:
				summary.cached += 1
				continue
			pending.append(dataset_id)
		if pending:
			self.check_reachable()
		for dataset_id in tqdm(
			pending, desc="Converting supporting files", unit="dataset"
		):
			result: ConversionResult | None = self.convert(store, dataset_id)
			if result is None:
				summary.failed.append(dataset_id)
				continue
			summary.converted += 1
			summary.file_errors += len(result.errors)
		return summary


def _warn_duplicate_names(folder: Path, dataset_id: str) -> None:
	"""Legilo keys results by file name, so only one of two same-named files can come back."""
	names: Counter[str] = Counter(p.name for p in folder.rglob("*") if p.is_file())
	for name, count in names.items():
		if count > 1:
			logger.warning(
				"Dataset %s has %d supporting files named %s; Legilo returns only one",
				dataset_id,
				count,
				name,
			)
