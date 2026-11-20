"""Relation records: one per dataset and related concept, for exact grouped counts.

Redis groups a document under only one value of a multi-value field, so grouping chunks by
`links` or `themes` undercounts. These records hold one related concept each instead.
"""

from typing import Any

from serka.okf.bundle import BundleFile
from serka.okf.chunks import dataset_fields

KINDS = ("person", "organisation", "grant", "funder", "theme")
_CONTRIBUTOR_KINDS = {"people": "person", "organisations": "organisation"}


def _record(dataset: BundleFile, kind: str, target: str, titles: dict[str, str], roles: list[str]) -> dict[str, Any]:
	return {
		"dataset": dataset.id,
		"kind": kind,
		"target": target,
		"target_title": titles.get(target, target),
		"roles": roles,
		"links": dataset.links,
		**dataset_fields(dataset.meta),
	}


def relation_records(files: list[BundleFile]) -> list[dict[str, Any]]:
	"""Records with an `id` of `<dataset-id>#<n>`, from each dataset's relation frontmatter keys."""
	titles = {f.id: str(f.meta.get("title") or f.id) for f in files if f.is_concept}
	records: list[dict[str, Any]] = []
	for f in files:
		if not f.is_concept or f.meta.get("type") != "dataset":
			continue
		rows: dict[tuple[str, str], dict[str, Any]] = {}
		for contributor in f.meta.get("contributors") or []:
			target = str(contributor.get("id") or "")
			kind = _CONTRIBUTOR_KINDS.get(target.split("/", 1)[0])
			if not kind:
				continue
			roles = [str(r) for r in contributor.get("roles") or []]
			if (kind, target) in rows:
				merged = rows[(kind, target)]["roles"]
				merged.extend(r for r in roles if r not in merged)
			else:
				rows[(kind, target)] = _record(f, kind, target, titles, roles)
		for kind, key in (("grant", "grants"), ("funder", "funders"), ("theme", "themes")):
			for target in dict.fromkeys(str(t) for t in f.meta.get(key) or []):
				rows.setdefault((kind, target), _record(f, kind, target, titles, []))
		records.extend({"id": f"{f.id}#{n}", **row} for n, row in enumerate(rows.values()))
	return records
