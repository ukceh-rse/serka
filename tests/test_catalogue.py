"""Unit tests for the MCP server's catalogue search: filter expressions, query text and warnings."""

import sys
from pathlib import Path
from typing import Any

import pytest
import redis

MCP_SRC = Path(__file__).resolve().parent.parent / "mcp-server" / "src" / "serka-mcp"
sys.path.insert(0, str(MCP_SRC))

from catalogue import (  # noqa: E402
	Catalogue,
	CatalogueError,
	Filters,
	epoch_days,
	escape_tag,
	filter_expression,
	normalise_id,
	text_clause,
)
from models import BoundingBox  # noqa: E402


def test_escape_tag() -> None:
	assert escape_tag("people/0000-0002-1825-009X") == "people\\/0000\\-0002\\-1825\\-009X"
	assert escape_tag("dataset") == "dataset"


def test_type_theme_and_linked_filters() -> None:
	expr = filter_expression(Filters(type="dataset", theme="themes/abc", linked="/people/x-1"))
	assert expr == "@type:{dataset} @themes:{themes\\/abc} @links:{people\\/x\\-1}"


def test_bounding_box_overlap_is_expanded() -> None:
	box = BoundingBox(south=54.0, north=55.0, west=-3.0, east=-2.0)
	expr = filter_expression(Filters(bounding_box=box))
	# 20% expansion: 0.1 on each side of a 1-degree box
	assert expr == "@north:[53.9 +inf] @south:[-inf 55.1] @east:[-3.1 +inf] @west:[-inf -1.9]"


def test_dates_are_epoch_days_and_inclusive() -> None:
	expr = filter_expression(Filters(published_after="2015-01-01", published_before="2020-12-31"))
	assert expr == f"@published:[{epoch_days('2015-01-01')} +inf] @published:[-inf {epoch_days('2020-12-31')}]"
	assert epoch_days("1970-01-02") == 1


def test_min_citations_and_lead() -> None:
	assert filter_expression(Filters(min_citations=5), lead=True) == "@citations:[5 +inf] @lead:[1 1]"


def test_no_filters() -> None:
	assert filter_expression(Filters()) == ""


def test_text_clause_ors_terms_and_drops_stopwords() -> None:
	assert text_clause("Pike in Windermere?", "@type:{dataset}") == "@text|title:(pike|windermere) @type:{dataset}"


def test_text_clause_escapes_by_keeping_only_words() -> None:
	assert text_clause('soil "carbon" (C) -uplands @x', "") == "@text|title:(soil|carbon|c|uplands|x)"


def test_stopword_only_query_matches_everything_the_filters_allow() -> None:
	assert text_clause("the of", "@type:{person}") == "@type:{person}"
	assert text_clause("?!", "") == "*"


def test_normalise_id() -> None:
	assert normalise_id("/people/x") == "people/x"
	assert normalise_id("people/x.md") == "people/x"
	assert normalise_id("/ontology/") == "ontology"


# --- warnings (4.4) ---------------------------------------------------------------------


class StubCatalogue(Catalogue):
	"""Records which search mode ran; the hybrid query can be made to fail with a syntax error."""

	def __init__(self, hybrid_error: str | None = None) -> None:
		super().__init__(client=None, embed=lambda _: [0.0])  # ty: ignore[invalid-argument-type]
		self.hybrid_error = hybrid_error
		self.calls: list[str] = []

	def _hybrid(self, query: str, filters_expr: str, limit: int, window: int, sort: Any = None):  # type: ignore[override]
		self.calls.append("hybrid")
		if self.hybrid_error:
			raise redis.ResponseError(self.hybrid_error)
		return [{"__key": "chunk:people/x#0"}], 1, [0.5]

	def _vector_only(self, query: str, filters_expr: str, limit: int, window: int):  # type: ignore[override]
		self.calls.append("vector")
		return [{"__key": "chunk:people/x#0"}], 1, [0.9]

	def _sorted(self, filters_expr: str, sort_by: Any, order: Any, limit: int):  # type: ignore[override]
		self.calls.append("sorted")
		return [{"__key": "chunk:people/x#0"}], 1

	def _hits(self, keys: list[str], scores: list[float]) -> list[dict[str, Any]]:
		return [{"chunk_id": k, "score": s} for k, s in zip(keys, scores)]


@pytest.mark.parametrize(
	("filters", "name"),
	[
		(Filters(type="person", bounding_box=BoundingBox(south=1, north=2, west=1, east=2)), "bounding_box"),
		(Filters(type="person", theme="themes/x"), "theme"),
		(Filters(type="grant", published_after="2020-01-01"), "published_after"),
		(Filters(type="organisation", min_citations=1), "min_citations"),
	],
)
def test_dataset_only_filter_with_other_type_has_no_hits_and_a_warning(filters: Filters, name: str) -> None:
	catalogue = StubCatalogue()
	result = catalogue.search("jane", filters=filters)
	assert result.hits == [] and result.total == 0
	assert len(result.warnings) == 1 and name in result.warnings[0]
	assert catalogue.calls == []


def test_dataset_only_filter_with_document_type_is_allowed() -> None:
	result = StubCatalogue().search("nets", filters=Filters(type="document", theme="themes/x"))
	assert result.warnings == [] and result.hits


def test_sort_with_non_dataset_type_warns_but_runs() -> None:
	catalogue = StubCatalogue()
	result = catalogue.search(sort_by="citations", filters=Filters(type="person"))
	assert catalogue.calls == ["sorted"]
	assert len(result.warnings) == 1 and "sort_by" in result.warnings[0]


def test_syntax_error_is_retried_as_vector_only() -> None:
	catalogue = StubCatalogue(hybrid_error="SEARCH_SYNTAX Syntax error at offset 1 near pike")
	result = catalogue.search("pike")
	assert catalogue.calls == ["hybrid", "vector"]
	assert result.hits == [{"chunk_id": "chunk:people/x#0", "score": 0.9}]
	assert "vector search only" in result.warnings[0]


def test_other_redis_errors_are_raised() -> None:
	with pytest.raises(redis.ResponseError):
		StubCatalogue(hybrid_error="Index not found").search("pike")


def test_neither_query_nor_sort_is_an_error() -> None:
	with pytest.raises(CatalogueError, match="query, a sort_by"):
		StubCatalogue().search("  ")


# --- aggregate warnings and errors (12.5) -----------------------------------------------


class StubAggregates(Catalogue):
	"""Records the aggregate requests made; every request returns no rows."""

	def __init__(self) -> None:
		super().__init__(client=None, embed=lambda _: [0.0])  # ty: ignore[invalid-argument-type]
		self.requests: list[tuple[str, str]] = []

	def _aggregate(self, index: str, request: Any) -> list[dict[str, Any]]:  # type: ignore[override]
		self.requests.append((index, request._query))
		return []

	def roles_in_use(self) -> list[str]:
		return ["author", "contact-person"]


@pytest.mark.parametrize("group_by", [None, "person", "year"])
def test_aggregate_dataset_only_filter_with_other_type_counts_nothing(group_by: Any) -> None:
	catalogue = StubAggregates()
	result = catalogue.aggregate(group_by=group_by, filters=Filters(type="person", theme="themes/x"))
	assert result.total == 0 and result.groups == []
	assert "theme" in result.warnings[0]
	assert catalogue.requests == []


def test_aggregate_query_with_relation_group_warns_and_counts_nothing() -> None:
	catalogue = StubAggregates()
	result = catalogue.aggregate(group_by="funder", query="soil carbon")
	assert result.groups == [] and result.total_groups == 0
	assert "theme filter" in result.warnings[0]
	assert catalogue.requests == []


def test_aggregate_role_without_person_or_organisation_group_is_ignored() -> None:
	catalogue = StubAggregates()
	result = catalogue.aggregate(group_by="grant", role="author")
	assert "role only applies" in result.warnings[0]
	assert all("@roles" not in query for _, query in catalogue.requests)


def test_aggregate_unknown_role_lists_roles_in_use() -> None:
	with pytest.raises(CatalogueError, match="Roles in use: author, contact-person"):
		StubAggregates().aggregate(group_by="person", role="Editor")


def test_aggregate_role_names_are_normalised() -> None:
	catalogue = StubAggregates()
	catalogue.aggregate(group_by="person", role="Contact Person")
	assert catalogue.requests[0] == ("idx:relations", "@kind:{person} @roles:{contact\\-person}")


def test_aggregate_relation_group_with_other_type_warns() -> None:
	catalogue = StubAggregates()
	result = catalogue.aggregate(group_by="person", filters=Filters(type="person"))
	assert "counts datasets" in result.warnings[0]


def test_aggregate_unknown_group_by() -> None:
	with pytest.raises(CatalogueError, match="Unknown group_by"):
		StubAggregates().aggregate(group_by="colour")  # ty: ignore[invalid-argument-type]
