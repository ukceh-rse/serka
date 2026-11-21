import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import requests

from serka.build import build_bundle, select_datasets
from serka.legilo import LegiloConverter
from serka.okf.bundle import read_bundle
from serka.raw import ConversionResult, RawStore, build_order

DATA = Path(__file__).parent / "data"
WITH_DOCS = "1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"
WITHOUT_DOCS = "ae02f4e8-9486-4b47-93ef-e49dd9ddecd4"
LONG_MARKDOWN = "# Methods\n\n| site | count |\n|---|---|\n| a | 1 |\n\n" + "word " * 12_000


class NoNetwork(requests.Session):
	def get(self, url: str | bytes, *_: Any, **__: Any) -> Any:
		raise AssertionError(f"unexpected request to {url!r}")


def record(name: str) -> dict[str, Any]:
	return json.loads((DATA / f"eidc-{name}.json").read_text())


@pytest.fixture
def store(tmp_path: Path) -> RawStore:
	"""Two downloaded datasets; WITH_DOCS has one converted file and one recorded failure."""
	store = RawStore(tmp_path / "raw")
	zp = tmp_path / "sd.zip"
	with zipfile.ZipFile(zp, "w") as zf:
		zf.writestr("supporting-documents/methods.pdf", b"pdf")
		zf.writestr("supporting-documents/scan.pdf", b"scan")
	store.write_dataset(WITH_DOCS, record("1c2fe14e"), zp)
	store.write_dataset(WITHOUT_DOCS, record("ae02f4e8"), None)
	store.markdown_dir(WITH_DOCS).mkdir(parents=True)
	(store.markdown_dir(WITH_DOCS) / "methods.pdf.md").write_text(LONG_MARKDOWN)
	result = ConversionResult(converted=datetime.now(timezone.utc), errors={"scan.pdf": "scanned PDF rejected"})
	store.save_conversion(WITH_DOCS, result)
	store.save_order(build_order([WITH_DOCS, WITHOUT_DOCS], [WITH_DOCS, WITHOUT_DOCS]))
	return store


def offline_converter() -> LegiloConverter:
	return LegiloConverter("http://legilo.test", timedelta(seconds=1), NoNetwork())


def documents(bundle: Path) -> dict[str, Any]:
	return {f.meta["title"]: f for f in read_bundle(bundle) if f.meta.get("type") == "document"}


def test_build_holds_full_markdown_and_skips_failed_files(store: RawStore, tmp_path: Path) -> None:
	summary = build_bundle(store, None, tmp_path / "bundles" / "full", offline_converter())
	docs = documents(summary.bundle_dir)
	assert list(docs) == ["methods.pdf"]
	body = docs["methods.pdf"].body
	assert "| site | count |" in body
	assert body.count("word") == 12_000
	assert docs["methods.pdf"].meta["media_type"] == "application/pdf"
	assert summary.concepts["dataset"] == 2


def test_building_another_size_leaves_first_bundle_unchanged(store: RawStore, tmp_path: Path) -> None:
	one = tmp_path / "bundles" / "1"
	build_bundle(store, 1, one, offline_converter())
	before = {p: p.read_bytes() for p in one.rglob("*") if p.is_file()}
	build_bundle(store, 2, tmp_path / "bundles" / "2", offline_converter())
	assert {p: p.read_bytes() for p in one.rglob("*") if p.is_file()} == before
	datasets = [f.id for f in read_bundle(one) if f.meta.get("type") == "dataset"]
	assert datasets == [f"datasets/{WITH_DOCS}"]


def test_not_enough_datasets_downloaded(store: RawStore, tmp_path: Path) -> None:
	with pytest.raises(ValueError, match="Requested 5 datasets but only 2 of the first 2"):
		build_bundle(store, 5, tmp_path / "b", offline_converter())


def test_incomplete_dataset_blocks_build(store: RawStore) -> None:
	store.status_path(WITHOUT_DOCS).unlink()
	with pytest.raises(ValueError, match="only 1 of the first 2"):
		select_datasets(store, 2)


def test_no_order_means_download_first(tmp_path: Path) -> None:
	with pytest.raises(ValueError, match="run scripts/download.py first"):
		select_datasets(RawStore(tmp_path), 1)
