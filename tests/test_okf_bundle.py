import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from haystack import Document

from serka.graph.extractors import EntityExtractor
from serka.okf import concepts as okf_concepts
from serka.okf.concepts import Concept, build_concepts
from serka.okf.writer import write_bundle

DATA = Path(__file__).parent / "data"
PLASTICS = "https://catalogue.ceh.ac.uk/id/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"
CHERNOBYL = "https://catalogue.ceh.ac.uk/id/ae02f4e8-9486-4b47-93ef-e49dd9ddecd4"
LINK = re.compile(r"\]\((/[^)\s]+)\)")


def _records() -> list[dict[str, Any]]:
	return [json.loads((DATA / f).read_text()) for f in ("eidc-1c2fe14e.json", "eidc-ae02f4e8.json")]


def _doc(dataset_uri: str, filename: str, content: str) -> Document:
	return Document(content=content, meta={"uri": dataset_uri, "filename": filename, "field": "SUPPORTING_DOC"})


def _build(records: list[dict[str, Any]], documents: list[Document] = [], **extra_rels: list) -> dict[str, Concept]:
	extracted = EntityExtractor().run(data=records)
	rels = {**extracted["relationships"], **extra_rels}
	return {c.id: c for c in build_concepts(records, extracted["nodes"], rels, documents)}


def _frontmatter(text: str) -> dict[str, Any]:
	assert text.startswith("---\n")
	return yaml.safe_load(text.split("---\n", 2)[1]) or {}


# --- 2.2 rendering --------------------------------------------------------------------------


def test_dataset_frontmatter() -> None:
	concepts = _build(_records())
	meta = _frontmatter(concepts["datasets/ae02f4e8-9486-4b47-93ef-e49dd9ddecd4"].render())
	assert meta["type"] == "dataset"
	assert meta["title"].startswith("A 'Reference Site' in the Chernobyl Exclusion Zone")
	assert meta["description"].startswith("Data comprise radionuclide activity concentrations")
	assert meta["resource"] == CHERNOBYL
	assert "americium" in meta["tags"]
	assert meta["published"] == "2018-02-20"
	assert meta["citations"] == 4
	assert meta["bbox"] == {"north": 52.376, "south": 44.39, "east": 40.218, "west": 22.129}
	assert all(t.startswith("themes/") for t in meta["themes"])
	assert meta["temporal"] == {"start": "2005-07-01", "end": "2015-06-30"}
	assert "https://doi.org/10.5285/ae02f4e8-9486-4b47-93ef-e49dd9ddecd4" in meta["identifiers"]


def test_dataset_without_bounding_box_has_no_bbox_key() -> None:
	meta = _build(_records())["datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"].meta
	assert "bbox" not in meta
	assert meta["citations"] == 0


def test_dataset_body_sections() -> None:
	body = _build(_records())["datasets/ae02f4e8-9486-4b47-93ef-e49dd9ddecd4"].body
	assert body.index("## Description") < body.index("## Lineage") < body.index("## Contributors")
	assert "The sampling site (0.4 km2)" in body
	# Contributor links carry their role, linked to its ontology concept
	assert "[Beresford, N.A.](/people/0000-0002-8722-0238) — [author](/ontology/roles/author)" in body
	assert "[custodian](/ontology/roles/data-curator)" in body
	# Related dataset outside the bundle links to the catalogue, with the predicate named
	assert "- [is part of](/ontology/predicates/isPartOf): [3124e313" in body
	assert "## Cited by" in body and "](https://doi.org/10.1016/j.jenvrad.2015.12.027)" in body


def test_funding_and_grant_concept() -> None:
	concepts = _build(_records())
	body = concepts["datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"].body
	[grant] = [c for c in concepts.values() if c.meta["type"] == "grant"]
	assert f"[Grant NE/V010603/1](/{grant.id})" in body
	assert "[originating grant](/ontology/predicates/originatingGrant)" in body
	assert "[awarded by](/ontology/predicates/awards): [Natural Environment Research Council](/organisations/" in grant.body
	[funder] = [c for c in concepts.values() if c.meta.get("tags") == ["funder"]]
	assert funder.meta["type"] == "organisation"


def test_dataset_relation_keys_match_body_links() -> None:
	records = _records()[:1]
	extracted = EntityExtractor().run(data=records)
	rels = extracted["relationships"]
	# The author is also the point of contact
	rels["ASSOCIATED_WITH"].append((PLASTICS, "https://orcid.org/0000-0003-4460-5178", "pointOfContact"))
	concepts = {c.id: c for c in build_concepts(records, extracted["nodes"], rels, [])}
	dataset = concepts["datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"]
	meta = _frontmatter(dataset.render())
	assert meta["contributors"] == [
		{"id": "people/0000-0003-4460-5178", "roles": ["author", "contact-person"]},
		{"id": "organisations/04xw4m193", "roles": ["data-curator", "publisher", "distributor"]},
		{"id": "organisations/00n3w3b69", "roles": ["rights-holder"]},
	]
	[grant] = [c.id for c in concepts.values() if c.meta["type"] == "grant"]
	[funder] = [c.id for c in concepts.values() if c.meta.get("tags") == ["funder"]]
	assert meta["grants"] == [grant]
	# The funder is reached through the grant, not as a contributor
	assert meta["funders"] == [funder]
	linked = set(LINK.findall(dataset.body))
	for target in [c["id"] for c in meta["contributors"]] + meta["grants"] + meta["funders"]:
		assert f"/{target}" in linked
	for role in {r for c in meta["contributors"] for r in c["roles"]}:
		assert f"/ontology/roles/{role}" in linked


def test_shared_person_is_one_concept_linked_from_both_datasets() -> None:
	records = _records()
	author = next(a for a in records[0]["authors"] if a.get("nameIdentifier"))
	records[1]["authors"].append(author)
	concepts = _build(records)
	person_id = "people/" + author["nameIdentifier"].rsplit("/", 1)[1]
	assert concepts[person_id].meta["type"] == "person"
	linking = [c.id for c in concepts.values() if c.meta["type"] == "dataset" and f"(/{person_id})" in c.body]
	assert len(linking) == 2


def test_person_without_affiliation_has_no_body_or_description() -> None:
	record = {
		"uri": PLASTICS,
		"title": "T",
		"authors": [{"fullName": "Solo Person", "nameIdentifier": "https://orcid.org/0000-0000-0000-0001"}],
	}
	person = _build([record])["people/0000-0000-0000-0001"]
	assert person.body == ""
	assert "description" not in person.meta
	assert person.render() == (
		"---\ntype: person\ntitle: Solo Person\nresource: https://orcid.org/0000-0000-0000-0001\n---\n"
	)


def test_related_dataset_in_bundle_links_its_concept() -> None:
	records = _records()
	records[0]["relationships"] = [{"relation": "http://purl.org/dc/terms/isPartOf", "target": CHERNOBYL.rsplit("/", 1)[1]}]
	body = _build(records)["datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"].body
	assert "- [is part of](/ontology/predicates/isPartOf): [A 'Reference Site'" in body
	assert "](/datasets/ae02f4e8-9486-4b47-93ef-e49dd9ddecd4)" in body


def test_supporting_document_concept() -> None:
	docs = [_doc(PLASTICS, "methods.pdf", "Spherulite growth was imaged every minute.")]
	concepts = _build(_records(), docs)
	[doc] = [c for c in concepts.values() if c.meta["type"] == "document"]
	assert doc.id.startswith("datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d/docs/")
	assert doc.meta == {"type": "document", "title": "methods.pdf", "media_type": "application/pdf"}
	assert "Spherulite growth was imaged every minute." in doc.body
	assert "(/datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d)" in doc.body
	dataset = concepts["datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"]
	assert f"[methods.pdf](/{doc.id})" in dataset.body
	assert "[references](/ontology/predicates/references)" in dataset.body


def test_same_named_files_on_two_datasets_are_two_concepts() -> None:
	docs = [_doc(PLASTICS, "readme.txt", "plastics readme"), _doc(CHERNOBYL, "readme.txt", "chernobyl readme")]
	found = [c for c in _build(_records(), docs).values() if c.meta["type"] == "document"]
	assert len(found) == 2
	assert len({c.id for c in found}) == 2


def test_link_text_brackets_are_escaped() -> None:
	assert okf_concepts._link("A [draft] title", "/x") == "[A \\[draft\\] title](/x)"


# --- 2.3 theme hierarchy ----------------------------------------------------------------


def test_theme_ancestors_and_broader_links() -> None:
	fish, biodiversity, life = (f"http://www.eionet.europa.eu/gemet/concept/{n}" for n in (1, 2, 3))
	record = {"uri": PLASTICS, "title": "Fish", "keywordsTheme": [{"value": "Freshwater fish", "uri": fish}]}
	extracted = EntityExtractor().run(data=[record])
	nodes = {
		**extracted["nodes"],
		"Concept": [
			*extracted["nodes"]["Concept"],
			{"uri": biodiversity, "label": "Biodiversity", "scheme": "gemet"},
			{"uri": life, "label": "Life", "scheme": "gemet"},
		],
	}
	rels = {**extracted["relationships"], "BROADER": [(fish, biodiversity), (biodiversity, life)]}
	concepts = {c.id: c for c in build_concepts([record], nodes, rels, [])}

	ids = {uri: okf_concepts.ids.theme_id(uri) for uri in (fish, biodiversity, life)}
	assert concepts["datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"].meta["themes"] == sorted(ids.values())
	fish_concept = concepts[ids[fish]]
	assert fish_concept.meta["title"] == "Freshwater fish"
	assert f"[broader](/ontology/predicates/broader): [Biodiversity](/{ids[biodiversity]})" in fish_concept.body
	assert f"[Life](/{ids[life]})" in concepts[ids[biodiversity]].body
	# Only direct themes are listed in the dataset body
	dataset_body = concepts["datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"].body
	assert f"(/{ids[fish]})" in dataset_body and f"(/{ids[biodiversity]})" not in dataset_body


# --- 2.4 ontology concepts --------------------------------------------------------------


def test_used_role_has_ontology_concept() -> None:
	concept = _build(_records())["ontology/roles/data-curator"]
	assert concept.meta["type"] == "ontology"
	assert concept.meta["resource"] == "http://purl.org/spar/scoro/data-curator"
	assert "custodian" in concept.meta["description"]
	assert "`scoro:data-curator`" in concept.body
	assert "`scoro:DataRole`" in concept.body


def test_unused_terms_have_no_concept() -> None:
	concepts = _build(_records())
	assert "ontology/predicates/isPartOf" in concepts
	assert "ontology/roles/data-creator" not in concepts
	record = {"uri": PLASTICS, "title": "Lonely"}
	assert not [c for c in _build([record]) if c.startswith(("ontology/predicates/", "ontology/roles/"))]


def test_ontology_links_resolve_to_written_files(tmp_path: Path) -> None:
	concepts = list(_build(_records(), [_doc(PLASTICS, "m.pdf", "text")]).values())
	write_bundle(tmp_path / "bundle", concepts)
	for path in (tmp_path / "bundle").rglob("*.md"):
		for target in LINK.findall(path.read_text()):
			if target.startswith("/ontology/"):
				assert (tmp_path / "bundle" / f"{target[1:]}.md").exists(), f"{path}: {target}"


# --- 2.5 index files and conformance ----------------------------------------------------


def _resolves(bundle: Path, target: str) -> bool:
	rel = target.lstrip("/")
	return (bundle / f"{rel}.md").exists() or (bundle / rel / "index.md").exists() or (bundle / rel).is_file()


def test_bundle_conformance(tmp_path: Path) -> None:
	bundle = tmp_path / "bundle"
	write_bundle(bundle, list(_build(_records(), [_doc(PLASTICS, "m.pdf", "text")]).values()))

	assert _frontmatter((bundle / "index.md").read_text()) == {"okf_version": "0.2"}
	assert '---\nokf_version: "0.2"\n---\n' in (bundle / "index.md").read_text()
	for path in bundle.rglob("*.md"):
		if path.name in ("index.md", "log.md"):
			continue
		meta = _frontmatter(path.read_text())
		assert isinstance(meta.get("type"), str) and meta["type"], path
	indexes = list(bundle.rglob("index.md"))
	assert {p.relative_to(bundle).as_posix() for p in indexes} >= {"index.md", "datasets/index.md", "ontology/index.md"}
	for index in indexes:
		for target in LINK.findall(index.read_text()):
			assert _resolves(bundle, target), f"{index}: {target}"


def test_root_and_ontology_indexes(tmp_path: Path) -> None:
	bundle = tmp_path / "bundle"
	concepts = _build(_records())
	write_bundle(bundle, list(concepts.values()))
	root = (bundle / "index.md").read_text()
	assert "[Ontology](/ontology/index) — " in root
	assert "[Datasets](/datasets/index) — " in root
	ontology_index = (bundle / "ontology" / "index.md").read_text()
	for concept_id, concept in concepts.items():
		if concept_id.startswith("ontology/"):
			assert f"(/{concept_id}) — {concept.meta['description']}" in ontology_index


# --- 2.6 writer ----------------------------------------------------------------------


def _run_writer(bundle: Path, records: list[dict[str, Any]]) -> None:
	extracted = EntityExtractor().run(data=records)
	write_bundle(bundle, build_concepts(records, extracted["nodes"], extracted["relationships"], []))


def test_smaller_second_run_leaves_only_its_concepts(tmp_path: Path) -> None:
	bundle = tmp_path / "bundle"
	_run_writer(bundle, _records())
	assert (bundle / "datasets" / "ae02f4e8-9486-4b47-93ef-e49dd9ddecd4.md").exists()
	assert (bundle / "people" / "0000-0002-8722-0238.md").exists()

	_run_writer(bundle, _records()[:1])
	assert (bundle / "datasets" / "1c2fe14e-0aa4-4f4a-b827-57b96deeda0d.md").exists()
	assert not (bundle / "datasets" / "ae02f4e8-9486-4b47-93ef-e49dd9ddecd4.md").exists()
	assert not (bundle / "people" / "0000-0002-8722-0238.md").exists()
	assert not (bundle / "ontology" / "predicates" / "isPartOf.md").exists()
	assert sorted(p.name for p in tmp_path.iterdir()) == ["bundle"]


def test_failed_run_leaves_previous_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	bundle = tmp_path / "bundle"
	_run_writer(bundle, _records())
	before = sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob("*"))

	def broken_index(_: list[Concept]) -> dict[str, str]:
		raise RuntimeError("disk full")

	monkeypatch.setattr("serka.okf.writer.index_files", broken_index)
	with pytest.raises(Exception, match="disk full"):
		_run_writer(bundle, _records()[:1])
	assert sorted(p.relative_to(bundle).as_posix() for p in bundle.rglob("*")) == before
	assert sorted(p.name for p in tmp_path.iterdir()) == ["bundle"]
