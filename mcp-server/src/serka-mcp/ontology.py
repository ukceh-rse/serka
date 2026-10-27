"""DOO mapping, loaded from doo_mapping.json (the single source of truth; copies under
src/serka/ and ui/src/ are kept identical by scripts/sync-doo-mapping.py)."""

import json
from pathlib import Path
from typing import Any

MAPPING: dict[str, Any] = json.loads((Path(__file__).parent / "doo_mapping.json").read_text())

PREFIXES: dict[str, str] = MAPPING["prefixes"]
NODE_TYPES: dict[str, str] = MAPPING["node_types"]
RELATION_TYPES: dict[str, str] = MAPPING["relation_types"]
ROLES: dict[str, str] = MAPPING["roles"]
ROLE_CLASSES: dict[str, str] = MAPPING["role_classes"]
DEFINITIONS: dict[str, str] = MAPPING["definitions"]
DEFAULT_ROLE: str = MAPPING["default_role"]
DEFAULT_PREDICATE: str = MAPPING["default_predicate"]
PREDICATES: list[str] = MAPPING["predicates"]

JSONLD_CONTEXT: dict[str, Any] = {**PREFIXES, **MAPPING["terms"]}


def compact_iri(iri: str) -> str:
	"""Compact a full IRI to a CURIE using the known prefixes (e.g. dcterms:isPartOf)."""
	for prefix, ns in PREFIXES.items():
		if iri.startswith(ns) and len(iri) > len(ns):
			return f"{prefix}:{iri[len(ns):]}"
	return iri


def expand_curie(curie: str) -> str:
	"""Expand a CURIE to a full IRI using the known prefixes; unknown prefixes pass through."""
	prefix, _, local = curie.partition(":")
	return PREFIXES[prefix] + local if prefix in PREFIXES else curie


def role_individual(eidc_role: str | None) -> str:
	return ROLES.get(eidc_role or "", DEFAULT_ROLE)


def role_class(individual: str) -> str:
	return ROLE_CLASSES.get(individual, "pro:Role")


def _glossary(curies: list[str]) -> str:
	return "\n".join(f"  {c}: {DEFINITIONS[c]}" for c in curies if c in DEFINITIONS)


INSTRUCTIONS: str = f"""Serka searches the EIDC environmental data catalogue as a knowledge graph typed with the
Digital Objects Ontology (DOO {MAPPING["doo_version"]}). Results are JSON-LD: every entity has an @id (URI) and
@type (DOO class CURIE); keys are mapped to ontology terms by the @context. Call describe_ontology for
definitions and usage counts of every type, predicate and role.

Entity types (search return_type, get_relations target_type):
{_glossary(sorted(set(NODE_TYPES.values())))}

Predicates (get_relations predicate):
{_glossary(PREDICATES)}

Contributor roles follow DOO's pro:RoleInTime pattern: get_contributors returns the role individual (e.g. pro:author,
scoro:data-curator) and its class (e.g. pro:PublishingRole, scoro:DataRole); filter by either.
"""
