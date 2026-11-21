import io
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import requests

from serka.download import (
	EIDC_SEARCH_URL,
	DownloadRequest,
	download,
	download_dataset,
	list_published_ids,
	storing_gemet_lookup,
)
from serka.fetchers import ConceptHierarchyFetcher
from serka.raw import DatasetOrder, RawStore, parse_size, read_ids_file, size_name


class FakeResponse:
	def __init__(self, body: Any, status: int = 200, content: bytes = b"") -> None:
		self.body = body
		self.status_code = status
		self.content = content

	def json(self) -> Any:
		return self.body

	def raise_for_status(self) -> None:
		if self.status_code >= 400:
			raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession(requests.Session):
	"""Answers GETs from a {url: response} map, or by calling a function of (url, params)."""

	def __init__(self, answer: Any) -> None:
		super().__init__()
		self.answer = answer
		self.calls: list[tuple[Any, Any]] = []

	def get(self, url: str | bytes, params: Any = None, **_: Any) -> Any:
		self.calls.append((url, params))
		return self.answer(url, params)


def search_pages(pages: list[list[str]], num_found: int) -> FakeSession:
	def answer(_: str, params: dict[str, Any] | None) -> FakeResponse:
		page = (params or {})["page"]
		ids = pages[page - 1] if page <= len(pages) else []
		return FakeResponse(
			{"numFound": num_found, "results": [{"identifier": i} for i in ids]}
		)

	return FakeSession(answer)


def test_list_published_ids_pages_until_num_found() -> None:
	session = search_pages([["a", "b"], ["c"]], num_found=3)
	assert list_published_ids(session) == ["a", "b", "c"]
	assert [p["page"] for _, p in session.calls if p] == [1, 2]


def test_list_published_ids_fails_on_count_mismatch() -> None:
	session = search_pages([["a", "b"]], num_found=5)
	with pytest.raises(RuntimeError, match="reported 5 datasets but returned 2"):
		list_published_ids(session)


ZIP_PDF: bytes = b"%PDF-1.4 original bytes \x00\xff"


def zip_bytes(entries: dict[str, bytes]) -> bytes:
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w") as zf:
		for name, data in entries.items():
			zf.writestr(name, data)
	return buf.getvalue()


class StreamResponse(FakeResponse):
	def __enter__(self) -> "StreamResponse":
		return self

	def __exit__(self, *_: Any) -> None:
		return None

	def iter_content(self, chunk_size: int) -> Iterator[bytes]:
		for i in range(0, len(self.content), chunk_size):
			yield self.content[i : i + chunk_size]


def dataset_session(zip_response: StreamResponse) -> FakeSession:
	def answer(url: str, _: dict[str, Any] | None) -> FakeResponse:
		if "data-package" in url:
			return zip_response
		return FakeResponse({"id": "abc", "title": "Pike"})

	return FakeSession(answer)


def test_download_dataset_stores_original_files(tmp_path: Path) -> None:
	store = RawStore(tmp_path / "raw")
	zp = zip_bytes({"supporting-documents/methods.pdf": ZIP_PDF})
	session = dataset_session(StreamResponse({}, content=zp))
	status = download_dataset(session, store, "abc")
	assert status.has_supporting_docs
	assert (store.supporting_dir("abc") / "methods.pdf").read_bytes() == ZIP_PDF
	assert store.metadata("abc") == {"id": "abc", "title": "Pike"}
	assert [
		p.name for p in store.root.iterdir() if p.name.startswith(".download-")
	] == []


def test_download_dataset_without_zip(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	session = dataset_session(StreamResponse({}, status=404))
	status = download_dataset(session, store, "abc")
	assert store.is_complete("abc")
	assert not status.has_supporting_docs


def test_download_dataset_zip_without_supporting_folder(
	tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
	store = RawStore(tmp_path)
	session = dataset_session(
		StreamResponse({}, content=zip_bytes({"data/x.csv": b"1"}))
	)
	status = download_dataset(session, store, "abc")
	assert store.is_complete("abc")
	assert not status.has_supporting_docs
	assert "has no supporting-documents/ files" in caplog.text


def test_download_dataset_metadata_error_stores_nothing(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	session = FakeSession(lambda url, _: FakeResponse({}, status=500))
	with pytest.raises(requests.HTTPError):
		download_dataset(session, store, "abc")
	assert not store.is_complete("abc")


GEMET = "http://www.eionet.europa.eu/gemet/concept/"


def test_storing_gemet_lookup_fetches_once_then_reads_store(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	parents = [{"uri": f"{GEMET}4862", "preferredLabel": {"string": "livestock"}}]
	session = FakeSession(lambda url, params: FakeResponse(parents))
	lookup = storing_gemet_lookup(session, store)
	assert lookup(f"{GEMET}1225") == parents
	assert lookup(f"{GEMET}1225") == parents
	assert len(session.calls) == 1
	assert store.stored_gemet_broader(f"{GEMET}1225") == parents


def test_storing_gemet_lookup_does_not_store_errors(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	session = FakeSession(lambda url, params: FakeResponse({}, status=503))
	lookup = storing_gemet_lookup(session, store)
	with pytest.raises(requests.HTTPError):
		lookup(f"{GEMET}1225")
	assert not store.gemet_path(f"{GEMET}1225").exists()


def test_stored_lookup_gives_same_hierarchy_without_http(
	tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
	store = RawStore(tmp_path)
	parents = {
		f"{GEMET}1225": [
			{"uri": f"{GEMET}4862", "preferredLabel": {"string": "livestock"}}
		],
		f"{GEMET}4862": [
			{"uri": f"{GEMET}299", "preferredLabel": {"string": "animal"}}
		],
		f"{GEMET}299": [],
	}
	session = FakeSession(
		lambda url, params: FakeResponse(parents[params["concept_uri"]])
	)
	nodes = {"Concept": [{"uri": f"{GEMET}1225", "label": "cattle", "scheme": "gemet"}]}
	rels = {"HAS_THEME": [("d", f"{GEMET}1225")]}
	fetching = ConceptHierarchyFetcher(broader=storing_gemet_lookup(session, store))
	online = fetching.run(nodes=nodes, relationships=rels)
	calls = len(session.calls)
	offline = ConceptHierarchyFetcher(broader=store.stored_gemet_broader).run(
		nodes=nodes, relationships=rels
	)
	assert len(session.calls) == calls
	assert set(offline["relationships"]["BROADER"]) == set(
		online["relationships"]["BROADER"]
	)
	assert offline["nodes"] == online["nodes"]
	assert "not in the raw store" not in caplog.text
	ConceptHierarchyFetcher(
		broader=RawStore(tmp_path / "empty").stored_gemet_broader
	).run(nodes=nodes, relationships=rels)
	assert "not in the raw store" in caplog.text


def catalogue_session(
	published: list[str], broken: frozenset[str] = frozenset()
) -> FakeSession:
	"""EIDC search over `published`, records for each ID (HTTP 500 for `broken`), no zips, no GEMET."""

	def answer(url: str, params: dict[str, Any] | None) -> FakeResponse:
		if url == EIDC_SEARCH_URL:
			page = (params or {})["page"]
			ids = published if page == 1 else []
			return FakeResponse(
				{
					"numFound": len(published),
					"results": [{"identifier": i} for i in ids],
				}
			)
		if "data-package" in url:
			return StreamResponse({}, status=404)
		dataset_id = url.rsplit("/", 1)[-1].split("?")[0]
		if dataset_id in broken:
			return FakeResponse({}, status=500)
		return FakeResponse(
			{"id": dataset_id, "uri": f"https://catalogue.ceh.ac.uk/id/{dataset_id}"}
		)

	return FakeSession(answer)


def stored_order(store: RawStore) -> DatasetOrder:
	order = store.load_order()
	assert order is not None
	return order


def metadata_fetches(session: FakeSession) -> list[str]:
	return [u for u, _ in session.calls if "format=json" in u]


def test_download_grows_incrementally(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	published = [f"id{i}" for i in range(10)]
	first = catalogue_session(published)
	download(first, store, DownloadRequest(n=3))
	second = catalogue_session(published)
	summary = download(second, store, DownloadRequest(n=6))
	assert (summary.fetched, summary.skipped) == (3, 3)
	assert len(metadata_fetches(second)) == 3
	assert all(store.is_complete(i) for i in stored_order(store).first(6))


def test_failed_dataset_is_skipped_and_retried(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	published = ["a", "b", "c"]
	summary = download(
		catalogue_session(published, frozenset({"b"})),
		store,
		DownloadRequest(n=None, head=["a", "b", "c"]),
	)
	assert summary.failed == ["b"]
	assert (
		store.is_complete("a") and store.is_complete("c") and not store.is_complete("b")
	)
	retry = catalogue_session(published)
	summary = download(retry, store, DownloadRequest(n=None))
	assert (summary.fetched, summary.skipped) == (1, 2)


def test_existing_order_is_kept_and_extended(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	download(
		catalogue_session(["a", "b", "c"]), store, DownloadRequest(n=0, head=["c"])
	)
	order = stored_order(store)
	download(
		catalogue_session(["a", "b", "c", "d"]), store, DownloadRequest(n=0, head=["a"])
	)
	extended = stored_order(store)
	assert extended.ids == order.ids + ["d"]
	download(
		catalogue_session(["a", "b", "c", "d"]),
		store,
		DownloadRequest(n=0, head=["a"], reorder=True),
	)
	assert stored_order(store).ids[0] == "a"


def test_refresh_fetches_stored_datasets_again(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	download(catalogue_session(["a"]), store, DownloadRequest(n=None))
	again = catalogue_session(["a"])
	summary = download(again, store, DownloadRequest(n=None, refresh=True))
	assert summary.fetched == 1


@pytest.mark.parametrize(("value", "expected"), [("20", 20), ("all", None)])
def test_parse_size(value: str, expected: int | None) -> None:
	assert parse_size(value) == expected
	assert size_name(expected) == ("full" if expected is None else value)


def test_parse_size_rejects_zero() -> None:
	with pytest.raises(ValueError):
		parse_size("0")


def test_read_ids_file(tmp_path: Path) -> None:
	path = tmp_path / "ids.txt"
	path.write_text("# header\nabc  # pike\n\n def \n")
	assert read_ids_file(path) == ["abc", "def"]
