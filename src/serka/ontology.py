"""DOO mapping, loaded from doo_mapping.json: ingest's vocabulary for the bundle's ontology/ concepts."""

import json
from pathlib import Path
from typing import Any

MAPPING: dict[str, Any] = json.loads((Path(__file__).parent / "doo_mapping.json").read_text())

PREFIXES: dict[str, str] = MAPPING["prefixes"]
NODE_TYPES: dict[str, str] = MAPPING["node_types"]
DEFAULT_PREDICATE: str = MAPPING["default_predicate"]
ROLES: dict[str, str] = MAPPING["roles"]
DEFAULT_ROLE: str = MAPPING["default_role"]
ROLE_CLASSES: dict[str, str] = MAPPING["role_classes"]
DEFINITIONS: dict[str, str] = MAPPING["definitions"]


def compact_iri(iri: str) -> str:
	"""Compact a full IRI to a CURIE using the known prefixes (e.g. dcterms:isPartOf)."""
	for prefix, ns in PREFIXES.items():
		if iri.startswith(ns) and len(iri) > len(ns):
			return f"{prefix}:{iri[len(ns):]}"
	return iri
