"""DOO mapping, loaded from doo_mapping.json — a copy of
mcp-server/src/serka-mcp/doo_mapping.json kept identical by scripts/sync-doo-mapping.py."""

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

MAPPING: dict[str, Any] = json.loads((Path(__file__).parent / "doo_mapping.json").read_text())

PREFIXES: dict[str, str] = MAPPING["prefixes"]
NODE_TYPES: dict[str, str] = MAPPING["node_types"]
DEFAULT_PREDICATE: str = MAPPING["default_predicate"]

# Values are DOO node labels; callers map them to CURIEs via NODE_TYPES
ReturnType = StrEnum("ReturnType", {label: label for label in NODE_TYPES})  # type: ignore[misc]


def search_args(
	query: str,
	return_type: str | None = None,
	published_after: str | None = None,
	published_before: str | None = None,
) -> dict[str, Any]:
	"""Arguments for the MCP `search` tool; `return_type` is a NODE_TYPES label."""
	args: dict[str, Any] = {"query": query}
	if return_type:
		args["return_type"] = NODE_TYPES[return_type]
	if published_after:
		args["published_after"] = published_after
	if published_before:
		args["published_before"] = published_before
	return args


def compact_iri(iri: str) -> str:
	"""Compact a full IRI to a CURIE using the known prefixes (e.g. dcterms:isPartOf)."""
	for prefix, ns in PREFIXES.items():
		if iri.startswith(ns) and len(iri) > len(ns):
			return f"{prefix}:{iri[len(ns):]}"
	return iri
