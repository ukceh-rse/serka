from pathlib import Path

from serka.okf.bundle import normalise_id, outgoing_links, read_bundle, split_frontmatter


def _write(root: Path, rel: str, text: str) -> None:
	path = root / rel
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(text)


def test_split_frontmatter() -> None:
	meta, body = split_frontmatter("---\ntype: person\ntitle: Jane\n---\n\nHello [x](/a)\n")
	assert meta == {"type": "person", "title": "Jane"}
	assert body == "Hello [x](/a)\n"


def test_no_frontmatter() -> None:
	assert split_frontmatter("# Title\n") == ({}, "# Title\n")


def test_normalise_id() -> None:
	assert normalise_id("/people/x") == "people/x"
	assert normalise_id("people/x") == "people/x"
	assert normalise_id("/people/x.md") == "people/x"
	assert normalise_id("/people/x#affiliations") == "people/x"
	assert normalise_id("https://orcid.org/0000") is None
	assert normalise_id("mailto:a@b") is None
	assert normalise_id("#top") is None


def test_links_with_and_without_leading_slash_and_broken_links() -> None:
	known = {"people/x", "organisations/y"}
	body = (
		"[X](/people/x) and [X again](people/x.md), "
		"[Y](organisations/y), [gone](/people/missing), [web](https://example.org)"
	)
	assert outgoing_links(body, known) == ["people/x", "organisations/y"]


def test_escaped_brackets_in_link_text() -> None:
	assert outgoing_links(r"[A \[draft\] title](/datasets/a)", {"datasets/a"}) == ["datasets/a"]


def test_read_bundle(tmp_path: Path) -> None:
	_write(tmp_path, "index.md", '---\nokf_version: "0.2"\n---\n\n- [People](/people/index)\n')
	_write(tmp_path, "people/index.md", "# People\n\n- [Jane](/people/jane)\n")
	_write(tmp_path, "people/jane.md", "---\ntype: person\ntitle: Jane\n---\n\n[Org](/organisations/o) [self](/people/jane)\n")
	_write(tmp_path, "organisations/o.md", "---\ntype: organisation\ntitle: O\n---\n")
	files = {f.id: f for f in read_bundle(tmp_path)}

	assert set(files) == {"index", "people/index", "people/jane", "organisations/o"}
	assert files["people/jane"].links == ["organisations/o"]
	assert files["people/jane"].is_concept
	assert not files["people/index"].is_concept
	assert not files["index"].is_concept
	assert files["index"].links == ["people/index"]
	assert files["organisations/o"].body == ""
	assert files["people/jane"].raw.startswith("---\ntype: person")
