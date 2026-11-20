"""Concept IDs: bundle paths without `.md`, derived from source identifiers so re-ingest is stable."""

import hashlib
import re

_ORCID = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])$")
_ROR = re.compile(r"ror\.org/([0-9a-z]+)/?$")


def uri_hash(uri: str) -> str:
	"""First 12 hex characters of the URI's SHA-256: stable, and keeps names out of paths."""
	return hashlib.sha256(uri.encode()).hexdigest()[:12]


def dataset_id(uri: str) -> str:
	"""`datasets/<eidc-id>`, the EIDC ID being the last segment of the catalogue URI."""
	return f"datasets/{uri.rstrip('/').rsplit('/', 1)[-1]}"


def person_id(uri: str) -> str:
	match = _ORCID.search(uri)
	return f"people/{match.group(1) if match else uri_hash(uri)}"


def organisation_id(uri: str) -> str:
	match = _ROR.search(uri)
	return f"organisations/{match.group(1) if match else uri_hash(uri)}"


def grant_id(uri: str) -> str:
	return f"grants/{uri_hash(uri)}"


def theme_id(uri: str) -> str:
	return f"themes/{uri_hash(uri)}"


def document_id(dataset_uri: str, source_id: str) -> str:
	"""A supporting file, under its dataset; `source_id` keeps same-named files distinct."""
	return f"{dataset_id(dataset_uri)}/docs/{source_id}"
