"""Neo4j rows -> DOO-typed JSON-LD models. Pure functions (no driver/app imports) so they
can be unit tested."""

from typing import Any, Optional

from models import (
	BaseEntity,
	ConceptEntity,
	DatasetEntity,
	Entity,
	ExpressionEntity,
	GrantEntity,
	ManifestationEntity,
	OrganisationEntity,
	PathStep,
	PeriodOfTime,
	PersonEntity,
	SearchHit,
)
from ontology import DEFAULT_PREDICATE, NODE_TYPES, RELATION_TYPES, compact_iri, role_individual

_LABEL_FOR_TYPE: dict[str, str] = {v: k for k, v in NODE_TYPES.items()}

# Most specific model first: a FundingAgency is also an Organisation.
_MODEL_FOR_LABEL: list[tuple[str, type[BaseEntity]]] = [
	("Dataset", DatasetEntity),
	("Person", PersonEntity),
	("Organisation", OrganisationEntity),
	("Grant", GrantEntity),
	("Concept", ConceptEntity),
	("Document", ExpressionEntity),
	("DigitalManifestation", ManifestationEntity),
]


def resolve_label(curie: str) -> Optional[str]:
	"""DOO class CURIE -> Neo4j label, or None if the class is not in the graph."""
	return _LABEL_FOR_TYPE.get(curie)


def _str(v: Any) -> Optional[str]:
	return None if v is None else str(v)


def _wkt_bbox(props: dict) -> Optional[str]:
	try:
		s, n = float(props["south_boundary"]), float(props["north_boundary"])
		w, e = float(props["west_boundary"]), float(props["east_boundary"])
	except (KeyError, TypeError, ValueError):
		return None
	return f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))"


def props_to_entity(labels: list[str], props: dict) -> Entity:
	types = [NODE_TYPES[label] for label in labels if label in NODE_TYPES]
	model = next((m for label, m in _MODEL_FOR_LABEL if label in labels), BaseEntity)
	common = {
		"id": props.get("uri") or None,
		"type": types,
		"label": props.get("title") or props.get("name") or props.get("label"),
	}
	if model is DatasetEntity:
		start, end = _str(props.get("temporal_start")), _str(props.get("temporal_end"))
		return DatasetEntity(
			**common,
			title=props.get("title"),
			publication_date=_str(props.get("publication_date")),
			identifiers=props.get("identifiers"),
			resource_type=props.get("resource_type"),
			access_rights=props.get("access_rights"),
			licence=props.get("licence"),
			temporal=PeriodOfTime(start_date=start, end_date=end) if start or end else None,
			bbox=_wkt_bbox(props),
			citations=props.get("citations"),
		)
	if model in (PersonEntity, OrganisationEntity):
		return model(**common, name=props.get("name"))
	if model is GrantEntity:
		return GrantEntity(
			**common, title=props.get("title"), grant_number=props.get("grant_number"), see_also=props.get("see_also")
		)
	if model is ConceptEntity:
		return ConceptEntity(**common, scheme=props.get("scheme"))
	if model is ExpressionEntity:
		return ExpressionEntity(**common, bibliographic_citation=props.get("bibliographic_citation"))
	if model is ManifestationEntity:
		return ManifestationEntity(**common, title=props.get("title"), format=props.get("format"))
	return BaseEntity(**common)


def rel_to_predicate(rel_type: str, rel_props: dict) -> str:
	if rel_type == "RELATION":
		return compact_iri(rel_props.get("predicate") or DEFAULT_PREDICATE)
	if rel_type == "ASSOCIATED_WITH":
		return role_individual(rel_props.get("role"))
	return RELATION_TYPES.get(rel_type, rel_type)


def build_search_hits(nodes: list[dict]) -> list[SearchHit]:
	hits = []
	for n in nodes:
		is_chunk = "TextChunk" in n["matched_labels"]
		matched_on = (n["matched_props"].get("field") or "text") if is_chunk else "metadata"
		excerpt = n["matched_props"].get("content") if is_chunk else None

		# Path nodes in graph order [matched, via..., target]; edges[i] joins chain[i]↔chain[i+1].
		chain = [(n["matched_labels"], n["matched_props"])]
		chain += [(v["labels"], v["props"]) for v in (n["via"] or [])]
		chain.append((n["target_labels"], n["target_props"]))
		edges = [(r["type"], r["props"]) for r in (n.get("rels") or [])]

		# A matched TextChunk is evidence, not an entity: its field/content is the match, so drop it
		# and its incident edge — the next node becomes the anchor of the relationship chain.
		if is_chunk and len(chain) > 1:
			chain = chain[1:]
			edges = edges[1:]

		entity = props_to_entity(*chain[-1])
		# Walk from the returned entity back to the anchor: edges[k] joins chain[k]↔chain[k+1].
		path = [
			PathStep(predicate=rel_to_predicate(*edges[k]), entity=props_to_entity(*chain[k]))
			for k in range(len(edges) - 1, -1, -1)
		]
		hits.append(SearchHit(entity=entity, score=n["score"], matched_on=matched_on, excerpt=excerpt, path=path))
	return hits


def rrf_merge(lists: list[list[SearchHit]], k: int = 60) -> list[SearchHit]:
	scores: dict[str, float] = {}
	items: dict[str, SearchHit] = {}
	for ranked_list in lists:
		for rank, hit in enumerate(ranked_list, start=1):
			# TextChunk hits have no URI; key them on their content so distinct chunks don't collapse.
			key = hit.entity.id or hit.excerpt or ""
			scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
			if key not in items:
				items[key] = hit
	return [items[k] for k in sorted(scores, key=lambda k: scores[k], reverse=True)]
