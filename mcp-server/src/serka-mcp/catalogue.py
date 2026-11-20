"""Search, aggregate and read over the OKF catalogue indexes in Redis (built by serka's bundle loader).

Three search modes:
  query, no sort_by    FT.HYBRID (BM25 + vector, RRF), one hit per chunk
  sort_by, no query    FT.SEARCH on lead chunks, SORTBY, one hit per concept, exact
  query + sort_by      FT.HYBRID on lead chunks over a wider window, then SORTBY

Aggregates (exact counts) use FT.AGGREGATE: totals, years and types on idx:chunks, and groups by
related concept on idx:relations, which has one record per dataset and related concept because
Redis groups a document under only one value of a multi-value field.
"""

import re
import struct
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Literal, Optional

import redis
from redis.commands.search.hybrid_query import (
	CombinationMethods,
	CombineResultsMethod,
	HybridFilter,
	HybridPostProcessingConfig,
	HybridQuery,
	HybridSearchQuery,
	HybridVsimQuery,
	VectorSearchMethods,
)
from redis.commands.search import reducers
from redis.commands.search.aggregation import AggregateRequest, Asc, Desc
from redis.commands.search.query import Query, SortbyField

from models import BoundingBox

INDEX = "idx:chunks"
RELATIONS_INDEX = "idx:relations"
CONCEPT_PREFIX = "concept:"
THEME_LABEL_PREFIX = "theme-label:"
RRF_CONSTANT = 60
DATASET_TYPES = ("dataset", "document")
SortField = Literal["citations", "published"]
Order = Literal["ascending", "descending"]
GroupBy = Literal["person", "organisation", "grant", "funder", "theme", "year", "type"]
GroupSort = Literal["datasets", "citations"]
RELATION_GROUPS = ("person", "organisation", "grant", "funder", "theme")
ROLE_GROUPS = ("person", "organisation")

# RediSearch's default English stopwords: a query of only these has no full-text terms
_STOPWORDS = frozenset(
	"a is the an and are as at be but by for if in into it no not of on or such that their then "
	"there these they this to was will with".split()
)
_EPOCH = date(1970, 1, 1)
_HIT_FIELDS = ("concept", "type", "title", "description", "resource", "text", "citations", "published_date")
# Indexed attributes loaded with hybrid results, so SORTBY and the vector-only fallback can order them
_SORT_LOADS = ("@citations", "@published")
# FT.AGGREGATE returns 10 rows unless given a LIMIT; years and types are few, so take them all
_ALL_GROUPS = 10_000


class CatalogueError(Exception):
	"""A caller error (unknown theme or concept, missing query and sort), reported as a tool error."""


@dataclass
class Filters:
	type: Optional[str] = None
	theme: Optional[str] = None  # resolved theme concept ID
	linked: Optional[str] = None
	bounding_box: Optional[BoundingBox] = None
	published_after: Optional[str] = None
	published_before: Optional[str] = None
	min_citations: Optional[int] = None

	def dataset_only(self) -> list[str]:
		"""Names of the set filters that only match datasets and their documents."""
		return [
			name
			for name in ("theme", "bounding_box", "published_after", "published_before", "min_citations")
			if getattr(self, name) is not None
		]


@dataclass
class SearchResult:
	hits: list[dict[str, Any]]
	total: int
	warnings: list[str] = field(default_factory=list)

	def dump(self) -> dict[str, Any]:
		return {"hits": self.hits, "total": self.total, "warnings": self.warnings}


@dataclass
class AggregateResult:
	total: int
	citations: Optional[int] = None
	groups: list[dict[str, Any]] = field(default_factory=list)
	total_groups: Optional[int] = None
	warnings: list[str] = field(default_factory=list)

	def dump(self) -> dict[str, Any]:
		out: dict[str, Any] = {"total": self.total}
		if self.citations is not None:
			out["citations"] = self.citations
		if self.total_groups is not None:
			out["groups"] = self.groups
			out["total_groups"] = self.total_groups
		out["warnings"] = self.warnings
		return out


def escape_tag(value: str) -> str:
	"""A TAG query value with punctuation and spaces escaped, e.g. `people/x-1` -> `people\\/x\\-1`."""
	return re.sub(r"([^A-Za-z0-9_])", r"\\\1", value)


def normalise_id(value: str) -> str:
	"""`/people/x`, `people/x.md` and `people/x/` all give `people/x`."""
	return value.strip().strip("/").removesuffix(".md").strip("/")


def epoch_days(iso_date: str) -> int:
	return (date.fromisoformat(iso_date[:10]) - _EPOCH).days


def text_terms(query: str) -> list[str]:
	"""Query words for the full-text side, without stopwords; word characters need no escaping."""
	return [w for w in re.findall(r"\w+", query.lower()) if w not in _STOPWORDS]


def filter_expression(filters: Filters, lead: bool = False) -> str:
	"""The filter part of a query, applied to both the full-text and the vector side."""
	parts = []
	if filters.type:
		parts.append(f"@type:{{{escape_tag(filters.type)}}}")
	if filters.theme:
		parts.append(f"@themes:{{{escape_tag(filters.theme)}}}")
	if filters.linked:
		parts.append(f"@links:{{{escape_tag(normalise_id(filters.linked))}}}")
	if filters.bounding_box:
		bb = filters.bounding_box.expand(20)
		parts += [
			f"@north:[{bb.south} +inf]",
			f"@south:[-inf {bb.north}]",
			f"@east:[{bb.west} +inf]",
			f"@west:[-inf {bb.east}]",
		]
	if filters.published_after:
		parts.append(f"@published:[{epoch_days(filters.published_after)} +inf]")
	if filters.published_before:
		parts.append(f"@published:[-inf {epoch_days(filters.published_before)}]")
	if filters.min_citations is not None:
		parts.append(f"@citations:[{int(filters.min_citations)} +inf]")
	if lead:
		parts.append("@lead:[1 1]")
	return " ".join(parts)


def text_clause(query: str, filters_expr: str) -> str:
	"""The `SEARCH` clause: any query term in text or title, plus the filters. A query with no
	terms (only stopwords or punctuation) matches every chunk the filters allow."""
	terms = text_terms(query)
	if not terms:
		return filters_expr or "*"
	return f"@text|title:({'|'.join(terms)}) {filters_expr}".strip()


def _decode(value: Any) -> Any:
	return value.decode() if isinstance(value, bytes) else value


def _concept(fields: dict[str, Any], tags: list[str]) -> dict[str, Any]:
	concept: dict[str, Any] = {
		"id": fields.get("concept"),
		"type": fields.get("type"),
		"title": fields.get("title"),
		"description": fields.get("description"),
		"resource": fields.get("resource"),
		"tags": tags,
	}
	if fields.get("citations") is not None:
		concept["citations"] = int(float(fields["citations"]))
	if fields.get("published_date"):
		concept["published"] = fields["published_date"]
	return concept


class Catalogue:
	def __init__(self, client: redis.Redis, embed: Callable[[str], list[float]]) -> None:
		self.client = client
		self.embed = embed

	# --- helpers -------------------------------------------------------------------------

	def resolve_theme(self, theme: str) -> str:
		"""A theme concept ID, or the ID stored for a theme label."""
		if "/" in theme:
			return normalise_id(theme)
		theme_id = self.client.get(f"{THEME_LABEL_PREFIX}{theme.strip().lower()}")
		if theme_id is None:
			raise CatalogueError(f"Unknown theme '{theme}'. Search with type 'theme' to find theme concepts.")
		return str(_decode(theme_id))

	def _hits(self, keys: list[str], scores: list[float]) -> list[dict[str, Any]]:
		"""Hits for chunk keys, with their fields read from the chunk JSON (not the embedding)."""
		pipe = self.client.pipeline(transaction=False)
		paths = [f"$.{f}" for f in (*_HIT_FIELDS, "tags")]
		for key in keys:
			pipe.json().get(key, *paths)
		hits = []
		for key, score, doc in zip(keys, scores, pipe.execute()):
			fields = {p.removeprefix("$."): (v[0] if v else None) for p, v in (doc or {}).items()}
			hits.append({
				"chunk_id": key.removeprefix("chunk:"),
				"text": fields.get("text") or "",
				"score": score,
				"concept": _concept(fields, fields.get("tags") or []),
			})
		return hits

	def _vector(self, query: str) -> bytes:
		vector = self.embed(query)
		return struct.pack(f"<{len(vector)}f", *vector)

	# --- search modes ----------------------------------------------------------------------

	def _hybrid(
		self, query: str, filters_expr: str, limit: int, window: int, sort: Optional[SortbyField] = None
	) -> tuple[list[dict[str, Any]], int, list[float]]:
		hq = HybridQuery(
			HybridSearchQuery(text_clause(query, filters_expr)),
			HybridVsimQuery(
				"@embedding",
				"$vec",
				vsim_search_method=VectorSearchMethods.KNN,
				vsim_search_method_params={"K": window},
				filter=HybridFilter(filters_expr) if filters_expr else None,
			),
		)
		post = HybridPostProcessingConfig().load("@__key", "@__score", *_SORT_LOADS, decode_field=True)
		if sort is not None:
			post.sort_by(sort)
		post.limit(0, limit)
		res = self.client.ft(INDEX).hybrid_search(
			hq,
			combine_method=CombineResultsMethod(CombinationMethods.RRF, WINDOW=window, CONSTANT=RRF_CONSTANT),
			post_processing=post,
			params_substitution={"vec": self._vector(query)},
		)
		rows = [{k: _decode(v) for k, v in r.items()} for r in res.results]
		scores = [float(r.get("__score") or 0.0) for r in rows]
		return rows, int(res.total_results), scores

	def _vector_only(
		self, query: str, filters_expr: str, limit: int, window: int
	) -> tuple[list[dict[str, Any]], int, list[float]]:
		"""Nearest chunks by vector alone, for when the full-text query cannot be parsed."""
		base = f"({filters_expr})" if filters_expr else "*"
		q = (
			Query(f"{base}=>[KNN {window} @embedding $vec AS distance]")
			.sort_by("distance")
			.return_fields("distance", "citations", "published")
			.paging(0, limit)
			.dialect(2)
		)
		res = self.client.ft(INDEX).search(q, query_params={"vec": self._vector(query)})
		rows = [{"__key": d.id, "citations": getattr(d, "citations", None), "published": getattr(d, "published", None)} for d in res.docs]
		scores = [1.0 - float(d.distance) for d in res.docs]
		return rows, min(int(res.total), window), scores

	def _sorted(
		self, filters_expr: str, sort_by: SortField, order: Order, limit: int
	) -> tuple[list[dict[str, Any]], int]:
		q = (
			Query(filters_expr)
			.sort_by(sort_by, asc=order == "ascending")
			.no_content()
			.paging(0, limit)
			.dialect(2)
		)
		res = self.client.ft(INDEX).search(q)
		rows = [{"__key": d.id} for d in res.docs]
		return rows, int(res.total)

	def search(
		self,
		query: Optional[str] = None,
		sort_by: Optional[SortField] = None,
		order: Order = "descending",
		filters: Optional[Filters] = None,
		limit: int = 25,
	) -> SearchResult:
		filters = filters or Filters()
		query = (query or "").strip()
		if not query and not sort_by:
			raise CatalogueError("search needs a query, a sort_by, or both.")
		limit = max(1, limit)
		warnings: list[str] = []

		dataset_only = filters.dataset_only()
		if dataset_only and filters.type and filters.type not in DATASET_TYPES:
			names = ", ".join(dataset_only)
			warnings.append(
				f"{names} only match datasets and their documents, so a search of type '{filters.type}' has no hits."
			)
			return SearchResult([], 0, warnings)
		if sort_by and filters.type and filters.type not in DATASET_TYPES:
			warnings.append(f"sort_by '{sort_by}' only orders datasets and documents; '{filters.type}' hits are unordered.")

		if sort_by and not query:
			rows, total = self._sorted(filter_expression(filters, lead=True), sort_by, order, limit)
			keys = [r["__key"] for r in rows]
			return SearchResult(self._hits(keys, [float(i + 1) for i in range(len(keys))]), total, warnings)

		sort = SortbyField(f"@{sort_by}", asc=order == "ascending") if sort_by else None
		window = max(50, 5 * limit) if sort_by else max(20, 2 * limit)
		filters_expr = filter_expression(filters, lead=bool(sort_by))
		try:
			rows, total, scores = self._hybrid(query, filters_expr, limit, window, sort)
		except redis.ResponseError as e:
			if "syntax" not in str(e).lower():
				raise
			warnings.append("Full-text search could not parse the query; results are from vector search only.")
			rows, total, scores = self._vector_only(query, filters_expr, limit, window)
			if sort_by:
				reverse = order == "descending"
				pairs = sorted(zip(rows, scores), key=lambda p: float(p[0].get(sort_by) or 0), reverse=reverse)
				rows, scores = [p[0] for p in pairs], [p[1] for p in pairs]
		if sort_by:
			scores = [float(i + 1) for i in range(len(rows))]
		return SearchResult(self._hits([r["__key"] for r in rows], scores), total, warnings)

	# --- aggregates -----------------------------------------------------------------------

	def _aggregate(self, index: str, request: AggregateRequest) -> list[dict[str, Any]]:
		rows = self.client.ft(index).aggregate(request).rows
		return [{_decode(r[i]): _decode(r[i + 1]) for i in range(0, len(r), 2)} for r in rows]

	def roles_in_use(self) -> list[str]:
		return sorted(str(_decode(v)) for v in self.client.ft(RELATIONS_INDEX).tagvals("roles"))

	def _per_dataset(self, query: str, filters: Filters) -> AggregateRequest:
		"""One row per matching dataset with its publication date and citations: lead chunks of
		datasets, or with a query, datasets with a full-text match in themselves or their documents."""
		rest = filter_expression(Filters(**{**filters.__dict__, "type": None}))
		if query:
			expr = text_clause(query, f"@type:{{dataset|document}} {rest}".strip())
		else:
			expr = f"@type:{{dataset}} @lead:[1 1] {rest}".strip()
		return AggregateRequest(expr).group_by(
			"@dataset",
			reducers.max("@published").alias("published"),
			reducers.max("@citations").alias("citations"),
		)

	def _per_concept(self, query: str, filters: Filters) -> AggregateRequest:
		"""One row per matching concept of any type, with its type."""
		expr = text_clause(query, filter_expression(filters)) if query else filter_expression(filters, lead=True)
		return AggregateRequest(expr).group_by("@concept", reducers.first_value("@type").alias("type"))

	def _relation_groups(
		self, group_by: str, role: Optional[str], sort_by: GroupSort, filters: Filters, limit: int
	) -> AggregateResult:
		parts = [f"@kind:{{{group_by}}}"]
		if role:
			parts.append(f"@roles:{{{escape_tag(role)}}}")
		parts.append(filter_expression(Filters(**{**filters.__dict__, "type": None})))
		expr = " ".join(p for p in parts if p)
		order = [Desc("@datasets"), Desc("@citations")] if sort_by == "datasets" else [Desc("@citations"), Desc("@datasets")]
		request = (
			AggregateRequest(expr)
			.load("$.target_title", "AS", "target_title")
			.group_by(
				"@target",
				reducers.count().alias("datasets"),
				reducers.sum("@citations").alias("citations"),
				reducers.first_value("@target_title").alias("title"),
			)
			.sort_by(*order, Asc("@title"), max=limit)
			.limit(0, limit)
		)
		groups = [
			{"id": r["target"], "title": r.get("title") or r["target"], "datasets": int(r["datasets"]), "citations": int(float(r.get("citations") or 0))}
			for r in self._aggregate(RELATIONS_INDEX, request)
		]
		totals = self._aggregate(
			RELATIONS_INDEX,
			AggregateRequest(expr).group_by(
				[], reducers.count_distinct("@target").alias("groups"), reducers.count_distinct("@dataset").alias("datasets")
			),
		)
		total_groups = int(totals[0]["groups"]) if totals else 0
		total = int(totals[0]["datasets"]) if totals else 0
		return AggregateResult(total=total, groups=groups, total_groups=total_groups)

	def aggregate(
		self,
		group_by: Optional[GroupBy] = None,
		role: Optional[str] = None,
		sort_by: GroupSort = "datasets",
		query: Optional[str] = None,
		filters: Optional[Filters] = None,
		limit: int = 10,
	) -> AggregateResult:
		filters = filters or Filters()
		query = " ".join(text_terms(query or ""))
		limit = max(1, limit)
		warnings: list[str] = []
		if group_by is not None and group_by not in (*RELATION_GROUPS, "year", "type"):
			raise CatalogueError(f"Unknown group_by '{group_by}'.")

		dataset_only = filters.dataset_only()
		if dataset_only and filters.type and filters.type not in DATASET_TYPES:
			names = ", ".join(dataset_only)
			warnings.append(f"{names} only match datasets and their documents, so nothing of type '{filters.type}' is counted.")
			return AggregateResult(total=0, groups=[], total_groups=0 if group_by else None, warnings=warnings)

		if role:
			role = role.strip().lower().replace(" ", "-")
			if group_by not in ROLE_GROUPS:
				warnings.append("role only applies to person and organisation groups; it was ignored.")
				role = None
			elif role not in (in_use := self.roles_in_use()):
				raise CatalogueError(f"Unknown role '{role}'. Roles in use: {', '.join(in_use)}.")

		if group_by in RELATION_GROUPS:
			if query:
				warnings.append(
					f"query cannot be combined with group_by '{group_by}'; use a theme filter to narrow the datasets instead."
				)
				return AggregateResult(total=0, groups=[], total_groups=0, warnings=warnings)
			if filters.type and filters.type != "dataset":
				warnings.append(f"group_by '{group_by}' counts datasets; type '{filters.type}' was ignored.")
			result = self._relation_groups(group_by, role, sort_by, filters, limit)
			result.warnings = warnings
			return result

		if group_by == "type":
			request = (
				self._per_concept(query, filters)
				.group_by("@type", reducers.count().alias("concepts"))
				.limit(0, _ALL_GROUPS)
			)
			rows = sorted(self._aggregate(INDEX, request), key=lambda r: (-int(r["concepts"]), r["type"]))
			groups = [{"id": r["type"], "title": r["type"], "concepts": int(r["concepts"])} for r in rows]
			total = sum(g["concepts"] for g in groups)
			return AggregateResult(total=total, groups=groups[:limit], total_groups=len(groups), warnings=warnings)

		datasets = filters.type in (None, "dataset")
		if group_by == "year":
			if not datasets:
				warnings.append(f"group_by 'year' counts datasets; type '{filters.type}' was ignored.")
			request = (
				self._per_dataset(query, filters)
				.filter("exists(@published)")
				.apply(year="floor(year(@published * 86400))")
				.group_by("@year", reducers.count().alias("datasets"), reducers.sum("@citations").alias("citations"))
				.sort_by(Asc("@year"), max=0)
				.limit(0, _ALL_GROUPS)
			)
			groups = [
				{"id": str(int(float(r["year"]))), "title": str(int(float(r["year"]))), "datasets": int(r["datasets"]), "citations": int(float(r.get("citations") or 0))}
				for r in self._aggregate(INDEX, request)
			]
			return AggregateResult(total=sum(g["datasets"] for g in groups), groups=groups, total_groups=len(groups), warnings=warnings)

		if datasets:
			request = self._per_dataset(query, filters).group_by(
				[], reducers.count().alias("datasets"), reducers.sum("@citations").alias("citations")
			)
			rows = self._aggregate(INDEX, request)
			total = int(rows[0]["datasets"]) if rows else 0
			citations = int(float(rows[0].get("citations") or 0)) if rows else 0
			return AggregateResult(total=total, citations=citations, warnings=warnings)
		request = self._per_concept(query, filters).group_by([], reducers.count().alias("concepts"))
		rows = self._aggregate(INDEX, request)
		return AggregateResult(total=int(rows[0]["concepts"]) if rows else 0, warnings=warnings)

	def read(self, concept_id: str) -> str:
		"""The markdown of a concept or index file; directories read as their `index`."""
		wanted = normalise_id(concept_id)
		candidates = [wanted, f"{wanted}/index"] if wanted else ["index"]
		if wanted.endswith("/index") or wanted == "index":
			candidates = [wanted]
		for candidate in candidates:
			text = self.client.get(f"{CONCEPT_PREFIX}{candidate}")
			if text is not None:
				return str(_decode(text))
		raise CatalogueError(f"No concept '{wanted or concept_id}' in the catalogue.")
