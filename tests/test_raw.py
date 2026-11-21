import zipfile
from pathlib import Path

import pytest

from serka.raw import RawStore, build_order, extend_order, extract_supporting_docs

PDF: bytes = b"%PDF-1.4 fake pdf bytes \x00\x01"


def make_zip(path: Path, entries: dict[str, bytes]) -> Path:
	with zipfile.ZipFile(path, "w") as zf:
		for name, data in entries.items():
			zf.writestr(name, data)
	return path


def test_dataset_without_status_is_incomplete(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	store.metadata_path("abc").parent.mkdir(parents=True)
	store.metadata_path("abc").write_text("{}")
	assert not store.is_complete("abc")


def test_write_dataset_stores_files_byte_for_byte(tmp_path: Path) -> None:
	store = RawStore(tmp_path / "raw")
	zp = make_zip(
		tmp_path / "abc.zip",
		{
			"supporting-documents/methods.pdf": PDF,
			"supporting-documents/sub/readme.txt": b"hi",
			"data/x.csv": b"1",
		},
	)
	status = store.write_dataset("abc", {"id": "abc"}, zp)
	assert store.is_complete("abc")
	assert status.has_supporting_docs
	assert (store.supporting_dir("abc") / "methods.pdf").read_bytes() == PDF
	assert (store.supporting_dir("abc") / "sub" / "readme.txt").read_bytes() == b"hi"
	assert not (store.supporting_dir("abc") / "x.csv").exists()
	assert store.metadata("abc") == {"id": "abc"}


def test_write_dataset_without_zip(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	status = store.write_dataset("abc", {"id": "abc"}, None)
	assert store.is_complete("abc")
	assert not status.has_supporting_docs
	assert store.supporting_dir("abc").is_dir()


def test_failed_write_leaves_no_partial_dataset(tmp_path: Path) -> None:
	store = RawStore(tmp_path / "raw")
	bad = tmp_path / "bad.zip"
	bad.write_bytes(b"not a zip")
	with pytest.raises(zipfile.BadZipFile):
		store.write_dataset("abc", {"id": "abc"}, bad)
	assert not store.is_complete("abc")
	assert not store.metadata_path("abc").exists()
	assert list(store.supporting_docs_root.iterdir()) == []


def test_refresh_replaces_previous_files(tmp_path: Path) -> None:
	store = RawStore(tmp_path / "raw")
	store.write_dataset(
		"abc",
		{},
		make_zip(tmp_path / "1.zip", {"supporting-documents/old.txt": b"old"}),
	)
	store.write_dataset(
		"abc",
		{},
		make_zip(tmp_path / "2.zip", {"supporting-documents/new.txt": b"new"}),
	)
	assert [p.name for p in store.supporting_dir("abc").iterdir()] == ["new.txt"]


def test_unsafe_zip_entries_are_skipped(tmp_path: Path) -> None:
	zp = make_zip(
		tmp_path / "evil.zip",
		{
			"supporting-documents/../../evil.txt": b"x",
			"supporting-documents/ok.txt": b"y",
		},
	)
	assert extract_supporting_docs(zp, tmp_path / "out") == 1
	assert not (tmp_path / "evil.txt").exists()


def test_order_prefixes_are_nested() -> None:
	order = build_order([f"id{i}" for i in range(200)], [])
	assert set(order.first(20)) <= set(order.first(100)) <= set(order.first(None))
	assert len(order.first(None)) == 200


def test_order_puts_ids_file_first() -> None:
	head = ["id5", "id1", "id5", "extra"]
	order = build_order([f"id{i}" for i in range(50)], head)
	assert order.ids[:3] == ["id5", "id1", "extra"]
	assert len(order.ids) == len(set(order.ids)) == 51


def test_order_is_reproducible_regardless_of_input_order() -> None:
	ids = [f"id{i}" for i in range(100)]
	assert build_order(ids, ["id3"], seed=7) == build_order(
		list(reversed(ids)), ["id3"], seed=7
	)
	assert build_order(ids, [], seed=7).ids != build_order(ids, [], seed=8).ids


def test_extend_order_appends_new_ids_only() -> None:
	order = build_order([f"id{i}" for i in range(30)], ["id2"])
	extended = extend_order(order, [f"id{i}" for i in range(35)])
	assert extended.ids[:30] == order.ids
	assert sorted(extended.ids[30:]) == ["id30", "id31", "id32", "id33", "id34"]


def test_order_round_trips_through_store(tmp_path: Path) -> None:
	store = RawStore(tmp_path)
	assert store.load_order() is None
	order = build_order(["a", "b", "c"], ["c"])
	store.save_order(order)
	assert store.load_order() == order
