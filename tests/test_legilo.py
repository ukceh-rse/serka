import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import requests

from serka.legilo import LegiloConverter
from serka.raw import RawStore

URL = "http://legilo.test"


class FakeResponse:
	def __init__(self, body: Any, status: int = 200) -> None:
		self.body = body
		self.status_code = status

	def json(self) -> Any:
		return self.body

	def raise_for_status(self) -> None:
		if self.status_code >= 400:
			raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeLegilo(requests.Session):
	"""Answers `/openapi.json` and `/{id}/documents` from canned bodies; an exception is raised."""

	def __init__(self, documents: dict[str, Any], up: bool = True) -> None:
		super().__init__()
		self.documents = documents
		self.up = up
		self.calls: list[str] = []

	def get(self, url: str | bytes, *_: Any, **__: Any) -> Any:
		self.calls.append(str(url))
		if not self.up:
			raise requests.ConnectionError("refused")
		if str(url).endswith("/openapi.json"):
			return FakeResponse({})
		answer = self.documents[str(url).split("/")[-2]]
		if isinstance(answer, Exception):
			raise answer
		return FakeResponse(answer)


def store_with(tmp_path: Path, files: dict[str, dict[str, bytes]]) -> RawStore:
	"""A raw store holding each dataset's supporting files (an empty dict means none)."""
	store = RawStore(tmp_path / "raw")
	for dataset_id, entries in files.items():
		zp: Path | None = None
		if entries:
			zp = tmp_path / f"{dataset_id}.zip"
			with zipfile.ZipFile(zp, "w") as zf:
				for name, data in entries.items():
					zf.writestr(f"supporting-documents/{name}", data)
		store.write_dataset(dataset_id, {"id": dataset_id}, zp)
	return store


def converter(session: FakeLegilo) -> LegiloConverter:
	return LegiloConverter(URL, timedelta(seconds=600), session)


def test_converts_and_caches_markdown(tmp_path: Path) -> None:
	store = store_with(
		tmp_path, {"abc": {"methods.docx": b"x", "scan.pdf": b"y"}, "none": {}}
	)
	legilo = FakeLegilo(
		{
			"abc": {
				"success": {"methods.docx": "# Methods\n\n| a | b |\n|---|---|"},
				"errors": {"scan.pdf": {"description": "scanned PDF rejected"}},
			}
		}
	)
	summary = converter(legilo).convert_all(store, ["abc", "none"])
	assert (summary.converted, summary.file_errors, summary.failed) == (1, 1, [])
	assert (
		(store.markdown_dir("abc") / "methods.docx.md")
		.read_text()
		.startswith("# Methods")
	)
	result = store.conversion("abc")
	assert result is not None and result.errors == {"scan.pdf": "scanned PDF rejected"}
	calls = len(legilo.calls)
	again = converter(legilo).convert_all(store, ["abc", "none"])
	assert len(legilo.calls) == calls
	assert again.cached == 1


def test_timeout_leaves_dataset_unconverted(tmp_path: Path) -> None:
	store = store_with(tmp_path, {"abc": {"big.pdf": b"x"}})
	legilo = FakeLegilo({"abc": requests.Timeout("read timed out")})
	summary = converter(legilo).convert_all(store, ["abc"])
	assert summary.failed == ["abc"]
	assert store.conversion("abc") is None


def test_unreachable_legilo_names_url(tmp_path: Path) -> None:
	store = store_with(tmp_path, {"abc": {"a.txt": b"x"}})
	with pytest.raises(ConnectionError, match=URL):
		converter(FakeLegilo({}, up=False)).convert_all(store, ["abc"])


def test_no_request_when_nothing_to_convert(tmp_path: Path) -> None:
	store = store_with(tmp_path, {"none": {}})
	legilo = FakeLegilo({}, up=False)
	converter(legilo).convert_all(store, ["none"])
	assert legilo.calls == []


def test_duplicate_file_name_warns(
	tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
	store = store_with(tmp_path, {"abc": {"a/readme.txt": b"1", "b/readme.txt": b"2"}})
	legilo = FakeLegilo({"abc": {"success": {"readme.txt": "2"}, "errors": {}}})
	summary = converter(legilo).convert_all(store, ["abc"])
	assert summary.converted == 1
	assert "2 supporting files named readme.txt" in caplog.text
