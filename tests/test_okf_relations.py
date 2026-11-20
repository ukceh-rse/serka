from serka.okf.bundle import BundleFile
from serka.okf.relations import relation_records

DATASET_META = {
	"type": "dataset",
	"title": "Pike",
	"published": "2020-01-02",
	"citations": 7,
	"themes": ["themes/fish", "themes/biodiversity"],
	"contributors": [
		{"id": "people/jane", "roles": ["author"]},
		{"id": "people/jane", "roles": ["contact-person"]},
		{"id": "organisations/eidc", "roles": ["data-curator"]},
		{"id": "elsewhere/x", "roles": ["author"]},
	],
	"grants": ["grants/g1"],
	"funders": ["organisations/nerc"],
}


def _files() -> list[BundleFile]:
	return [
		BundleFile("datasets/abc", "", DATASET_META, "", links=["people/jane", "grants/g1"]),
		BundleFile("people/jane", "", {"type": "person", "title": "Jane Smith"}, ""),
		BundleFile("datasets/abc/docs/s1", "", {"type": "document", "title": "a.pdf"}, ""),
	]


def test_one_record_per_dataset_and_related_concept() -> None:
	records = relation_records(_files())
	assert [(r["kind"], r["target"]) for r in records] == [
		("person", "people/jane"),
		("organisation", "organisations/eidc"),
		("grant", "grants/g1"),
		("funder", "organisations/nerc"),
		("theme", "themes/fish"),
		("theme", "themes/biodiversity"),
	]
	assert [r["id"] for r in records] == [f"datasets/abc#{n}" for n in range(6)]


def test_repeated_contributor_roles_are_merged() -> None:
	[jane] = [r for r in relation_records(_files()) if r["target"] == "people/jane"]
	assert jane["roles"] == ["author", "contact-person"]
	assert jane["target_title"] == "Jane Smith"


def test_records_carry_the_dataset_filter_fields() -> None:
	[grant] = [r for r in relation_records(_files()) if r["kind"] == "grant"]
	assert grant["dataset"] == "datasets/abc"
	assert grant["roles"] == []
	assert grant["target_title"] == "grants/g1"  # not in the bundle: the ID stands in
	assert grant["citations"] == 7
	assert grant["themes"] == ["themes/fish", "themes/biodiversity"]
	assert grant["links"] == ["people/jane", "grants/g1"]
	assert grant["published"] == 18263


def test_non_datasets_have_no_records() -> None:
	assert all(r["dataset"] == "datasets/abc" for r in relation_records(_files()))
