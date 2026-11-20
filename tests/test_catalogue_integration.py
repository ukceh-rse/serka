"""Search and read against a real Redis (TEST_REDIS_URL, default localhost:6380) holding a small
bundle embedded with the Bedrock model, so full-text, vector and fused ranking are all real."""

import os
import sys
from pathlib import Path
from typing import Any, Iterator

import pytest
import redis

from serka.graph.embedders import CachedDocumentEmbedder
from serka.okf.loader import load_bundle
from serka.settings import Settings

MCP_SRC = Path(__file__).resolve().parent.parent / "mcp-server" / "src" / "serka-mcp"
sys.path.insert(0, str(MCP_SRC))

from catalogue import Catalogue, CatalogueError, Filters  # noqa: E402

pytestmark = pytest.mark.integration

PIKE = "datasets/pike-windermere"
SOIL = "datasets/soil-carbon"
OLD_SOIL = "datasets/soil-survey-1978"
PEAT = "datasets/peat-depth"
METHODS = "datasets/pike-windermere/docs/methods"


def _dataset(
	title: str,
	description: str,
	published: str,
	citations: int,
	themes: list[str],
	body: str = "",
	contributors: dict[str, list[str]] | None = None,
	funders: list[str] | None = None,
) -> str:
	theme_lines = "".join(f"- {t}\n" for t in themes)
	relations = ""
	if contributors:
		relations += "contributors:\n" + "".join(f"- id: {c}\n  roles: [{', '.join(r)}]\n" for c, r in contributors.items())
	if funders:
		relations += "funders:\n" + "".join(f"- {f}\n" for f in funders)
	return (
		f"---\ntype: dataset\ntitle: {title}\ndescription: {description}\n"
		f"resource: https://catalogue.ceh.ac.uk/id/{title.lower().replace(' ', '-')}\ntags:\n- survey\n"
		f"published: '{published}'\ncitations: {citations}\n"
		"bbox:\n  north: 54.5\n  south: 54.2\n  east: -2.9\n  west: -3.0\n"
		f"themes:\n{theme_lines}{relations}---\n\n## Description\n\n{description}\n\n{body}"
	)


def _methods_text() -> str:
	filler = " ".join(f"step{i}" for i in range(160))
	gill = "Fyke nets were set overnight along the littoral margin to catch adult pike."
	return f"{gill} {filler} {gill} {filler} {gill}"


FILES = {
	"index.md": '---\nokf_version: "0.2"\n---\n\n- [Datasets](/datasets/index)\n- [Ontology](/ontology/index)\n',
	"datasets/index.md": "# Datasets\n",
	"ontology/index.md": "# Ontology\n\n- [data-curator](/ontology/roles/data-curator) — custodian role\n",
	f"{PIKE}.md": _dataset(
		"Pike in Windermere",
		"Annual counts of pike (Esox lucius) caught in gill nets in Windermere, sampling station WX-7741.",
		"2018-05-01",
		12,
		["themes/fish", "themes/biodiversity"],
		"Contributors: [Jane Smith](/people/jane) — [author](/ontology/roles/author)\n\n"
		"Supporting documents: [methods.pdf](/datasets/pike-windermere/docs/methods)",
		contributors={"people/jane": ["author", "contact-person"]},
		funders=["organisations/nerc"],
	),
	f"{METHODS}.md": "---\ntype: document\ntitle: methods.pdf\nmedia_type: application/pdf\n---\n\n"
	f"Supporting document of [Pike in Windermere](/{PIKE}).\n\n{_methods_text()}",
	f"{SOIL}.md": _dataset(
		"Soil carbon in upland grassland",
		"Topsoil organic carbon concentrations measured across upland grassland plots.",
		"2016-03-01",
		40,
		["themes/soil"],
		"Contributors: [Bob Jones](/people/bob) — author",
		contributors={"people/bob": ["author"]},
		funders=["organisations/nerc"],
	),
	f"{OLD_SOIL}.md": _dataset(
		"Soil survey of Cumbria 1978",
		"Historic soil pit descriptions and soil carbon from a county survey.",
		"1990-01-01",
		3,
		["themes/soil"],
		"Contributors: [Ann Lee](/people/ann) — author",
		contributors={"people/ann": ["author"]},
		funders=["organisations/nerc"],
	),
	f"{PEAT}.md": _dataset(
		"Peat depth survey",
		"Peat depth probed on a grid across a blanket bog, with soil carbon stock estimates.",
		"2021-09-01",
		25,
		["themes/soil"],
		"Contributors: [Ann Lee](/people/ann) — author",
		contributors={"people/ann": ["author"]},
		funders=["organisations/nerc", "organisations/bbsrc"],
	),
	"people/jane.md": "---\ntype: person\ntitle: Jane Smith\nresource: https://orcid.org/0000-0000-0000-0001\n---\n",
	"people/ann.md": "---\ntype: person\ntitle: Ann Lee\n---\n",
	"people/bob.md": "---\ntype: person\ntitle: Bob Jones\n---\n",
	"organisations/nerc.md": "---\ntype: organisation\ntitle: Natural Environment Research Council\ntags:\n- funder\n---\n",
	"organisations/bbsrc.md": "---\ntype: organisation\ntitle: BBSRC\ntags:\n- funder\n---\n",
	"themes/fish.md": "---\ntype: theme\ntitle: Freshwater fish\n---\n\n- [broader](/ontology/predicates/broader): [Biodiversity](/themes/biodiversity)\n",
	"themes/biodiversity.md": "---\ntype: theme\ntitle: Biodiversity\n---\n",
	"themes/soil.md": "---\ntype: theme\ntitle: Soil\n---\n",
	"ontology/roles/data-curator.md": "---\ntype: ontology\ntitle: data-curator\n"
	"description: The data curator role (\"custodian\").\ntags:\n- role\n---\n\n"
	"DOO identifier: `scoro:data-curator`. Used for the EIDC contributor role custodian.\n",
}


@pytest.fixture(scope="module")
def catalogue(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Catalogue]:
	client = redis.Redis.from_url(os.environ.get("TEST_REDIS_URL", "redis://localhost:6380"))
	try:
		client.ping()
	except redis.ConnectionError:
		pytest.skip("no test Redis; run: docker run -d -p 6380:6379 redis:8.10.3")
	settings = Settings()
	try:
		from haystack_integrations.components.embedders.amazon_bedrock import AmazonBedrockTextEmbedder

		text_embedder = AmazonBedrockTextEmbedder(model=settings.models_embedding)
		text_embedder.run(text="probe")
	except Exception as e:  # no AWS credentials or Bedrock access
		pytest.skip(f"Bedrock unavailable: {e}")

	root = tmp_path_factory.mktemp("bundle")
	for rel, text in FILES.items():
		(root / rel).parent.mkdir(parents=True, exist_ok=True)
		(root / rel).write_text(text)
	client.flushall()
	load_bundle(root, client, CachedDocumentEmbedder(model=settings.models_embedding))
	yield Catalogue(client, lambda text: list(text_embedder.run(text=text)["embedding"]))
	client.flushall()


def _concepts(hits: list[dict[str, Any]]) -> list[str]:
	return [h["concept"]["id"] for h in hits]


# --- 4.2 hybrid search ------------------------------------------------------------------


def test_exact_rare_term(catalogue: Catalogue) -> None:
	assert PIKE in _concepts(catalogue.search("WX-7741", limit=5).hits)


def test_paraphrase(catalogue: Catalogue) -> None:
	hits = catalogue.search("how many predatory freshwater fish live in the Lake District's largest lake", limit=3).hits
	assert PIKE in _concepts(hits)


def test_several_chunks_from_one_document(catalogue: Catalogue) -> None:
	hits = catalogue.search("fyke nets set overnight littoral margin", filters=Filters(type="document"), limit=10).hits
	doc_hits = [h for h in hits if h["concept"]["id"] == METHODS]
	assert len(doc_hits) >= 2
	assert len({h["chunk_id"] for h in doc_hits}) == len(doc_hits)


def test_hit_shape_and_order(catalogue: Catalogue) -> None:
	result = catalogue.search("pike windermere", limit=3)
	hit = next(h for h in result.hits if h["concept"]["id"] == PIKE)
	assert set(hit) == {"chunk_id", "text", "score", "concept"}
	assert hit["chunk_id"].startswith(f"{PIKE}#")
	assert hit["concept"] == {
		"id": PIKE,
		"type": "dataset",
		"title": "Pike in Windermere",
		"description": hit["concept"]["description"],
		"resource": "https://catalogue.ceh.ac.uk/id/pike-in-windermere",
		"tags": ["survey"],
		"citations": 12,
		"published": "2018-05-01",
	}
	scores = [h["score"] for h in result.hits]
	assert scores == sorted(scores, reverse=True)
	assert result.total >= len(result.hits)


def test_type_filter_applies_to_both_sides(catalogue: Catalogue) -> None:
	# The query names a person, so the nearest vectors and best text matches are the person concept
	hits = catalogue.search("Jane Smith", filters=Filters(type="dataset"), limit=10).hits
	assert hits and all(h["concept"]["type"] == "dataset" for h in hits)


def test_no_matches_returns_an_empty_list(catalogue: Catalogue) -> None:
	result = catalogue.search("pike", filters=Filters(type="grant"))
	assert result.hits == [] and result.total == 0


def test_ontology_concept_is_searchable(catalogue: Catalogue) -> None:
	assert "ontology/roles/data-curator" in _concepts(catalogue.search("custodian role", limit=5).hits)


def test_concept_with_no_body_is_found_by_name(catalogue: Catalogue) -> None:
	assert "people/jane" in _concepts(catalogue.search("Jane Smith", filters=Filters(type="person")).hits)


def test_broader_theme_and_linked_filters(catalogue: Catalogue) -> None:
	theme = catalogue.resolve_theme("Biodiversity")
	by_label = catalogue.search("counts", filters=Filters(type="dataset", theme=theme)).hits
	assert set(_concepts(by_label)) == {PIKE}
	# A dataset's documents inherit its themes
	assert METHODS in _concepts(catalogue.search("fyke nets", filters=Filters(theme=theme)).hits)
	linked = catalogue.search("survey", filters=Filters(linked="/people/jane")).hits
	assert set(_concepts(linked)) == {PIKE}


def test_bounding_box_includes_supporting_documents(catalogue: Catalogue) -> None:
	from models import BoundingBox

	box = BoundingBox(south=54.3, north=54.4, west=-2.98, east=-2.95)
	hits = catalogue.search("fyke nets", filters=Filters(bounding_box=box), limit=20).hits
	assert METHODS in _concepts(hits)
	assert all(h["concept"]["type"] in ("dataset", "document") for h in hits)


def test_unknown_theme_label(catalogue: Catalogue) -> None:
	with pytest.raises(CatalogueError, match="Unknown theme 'Volcanoes'"):
		catalogue.resolve_theme("Volcanoes")


# --- 4.3 sorted search ------------------------------------------------------------------


def test_most_cited_dataset(catalogue: Catalogue) -> None:
	result = catalogue.search(sort_by="citations", filters=Filters(type="dataset"), limit=1)
	assert _concepts(result.hits) == [SOIL]
	assert result.hits[0]["score"] == 1.0
	assert result.total == 4


def test_sort_with_theme_and_date_filters(catalogue: Catalogue) -> None:
	filters = Filters(type="dataset", theme="themes/soil", published_after="2015-01-01")
	assert _concepts(catalogue.search(sort_by="citations", filters=filters).hits) == [SOIL, PEAT]


def test_sorted_search_returns_one_hit_per_concept(catalogue: Catalogue) -> None:
	hits = catalogue.search(sort_by="published", limit=50).hits
	assert len(_concepts(hits)) == len(set(_concepts(hits)))
	assert _concepts(hits).count(METHODS) <= 1


def test_ascending_published(catalogue: Catalogue) -> None:
	hits = catalogue.search(sort_by="published", order="ascending", filters=Filters(type="dataset")).hits
	assert _concepts(hits) == [OLD_SOIL, SOIL, PIKE, PEAT]


def test_query_plus_sort(catalogue: Catalogue) -> None:
	# The relevance window (at least 50 lead chunks) covers this whole small catalogue
	hits = catalogue.search("soil carbon", sort_by="citations", filters=Filters(type="dataset"), limit=3).hits
	assert _concepts(hits) == [SOIL, PEAT, PIKE]
	assert [h["concept"]["citations"] for h in hits] == [40, 25, 12]
	assert [h["score"] for h in hits] == [1.0, 2.0, 3.0]


def test_neither_query_nor_sort(catalogue: Catalogue) -> None:
	with pytest.raises(CatalogueError):
		catalogue.search()


# --- 4.5 read ---------------------------------------------------------------------------


def test_read_concept(catalogue: Catalogue) -> None:
	text = catalogue.read("/people/jane")
	assert text == FILES["people/jane.md"]
	assert catalogue.read("people/jane.md") == text


def test_read_index(catalogue: Catalogue) -> None:
	assert catalogue.read("ontology/index") == FILES["ontology/index.md"]
	assert catalogue.read("/ontology/") == FILES["ontology/index.md"]
	assert catalogue.read("/") == FILES["index.md"]


def test_read_unknown(catalogue: Catalogue) -> None:
	with pytest.raises(CatalogueError, match="datasets/does-not-exist"):
		catalogue.read("datasets/does-not-exist")


# --- aggregates -------------------------------------------------------------------------


def test_total_datasets(catalogue: Catalogue) -> None:
	result = catalogue.aggregate()
	assert result.total == 4
	assert result.citations == 12 + 40 + 3 + 25


def test_top_author(catalogue: Catalogue) -> None:
	result = catalogue.aggregate(group_by="person", role="author", limit=1)
	assert result.groups == [{"id": "people/ann", "title": "Ann Lee", "datasets": 2, "citations": 28}]
	assert result.total_groups == 3


def test_most_cited_author(catalogue: Catalogue) -> None:
	groups = catalogue.aggregate(group_by="person", role="author", sort_by="citations").groups
	assert [(g["id"], g["citations"]) for g in groups] == [("people/bob", 40), ("people/ann", 28), ("people/jane", 12)]


def test_two_roles_on_one_dataset_count_once(catalogue: Catalogue) -> None:
	groups = catalogue.aggregate(group_by="person").groups
	assert {g["id"]: g["datasets"] for g in groups}["people/jane"] == 1
	contacts = catalogue.aggregate(group_by="person", role="contact person").groups
	assert [g["id"] for g in contacts] == ["people/jane"]


def test_grouped_with_filters(catalogue: Catalogue) -> None:
	soil = catalogue.resolve_theme("Soil")
	result = catalogue.aggregate(group_by="funder", filters=Filters(theme=soil, published_after="2015-01-01"))
	assert [(g["id"], g["datasets"]) for g in result.groups] == [("organisations/nerc", 2), ("organisations/bbsrc", 1)]
	assert result.total == 2


def test_grouped_counts_match_link_filters(catalogue: Catalogue) -> None:
	for g in catalogue.aggregate(group_by="person").groups:
		searched = catalogue.search(sort_by="citations", filters=Filters(type="dataset", linked=g["id"])).total
		assert g["datasets"] == searched, g["id"]


def test_broader_theme_counts_narrower_datasets(catalogue: Catalogue) -> None:
	groups = {g["id"]: g["datasets"] for g in catalogue.aggregate(group_by="theme").groups}
	assert groups["themes/biodiversity"] == 1  # the pike dataset, whose own theme is freshwater fish
	assert groups["themes/soil"] == 3


def test_per_year(catalogue: Catalogue) -> None:
	result = catalogue.aggregate(group_by="year")
	assert [(g["id"], g["datasets"]) for g in result.groups] == [("1990", 1), ("2016", 1), ("2018", 1), ("2021", 1)]
	assert result.total == 4


def test_catalogue_overview(catalogue: Catalogue) -> None:
	groups = {g["id"]: g["concepts"] for g in catalogue.aggregate(group_by="type").groups}
	assert groups == {"dataset": 4, "document": 1, "person": 3, "organisation": 2, "theme": 3, "ontology": 1}


def test_mentions_in_a_supporting_document_count_the_dataset_once(catalogue: Catalogue) -> None:
	# "fyke" appears only in the pike dataset's methods document, in several chunks
	assert catalogue.aggregate(query="fyke").total == 1
	assert catalogue.aggregate(query="soil carbon").total == 3


def test_counting_other_types(catalogue: Catalogue) -> None:
	assert catalogue.aggregate(filters=Filters(type="person")).total == 3
	assert catalogue.aggregate(query="fyke", filters=Filters(type="document")).total == 1


def test_query_with_a_relation_group_warns(catalogue: Catalogue) -> None:
	result = catalogue.aggregate(group_by="person", query="soil")
	assert result.groups == [] and "theme" in result.warnings[0]


def test_unknown_role_lists_roles_in_use(catalogue: Catalogue) -> None:
	with pytest.raises(CatalogueError, match="author, contact-person"):
		catalogue.aggregate(group_by="person", role="editor")
