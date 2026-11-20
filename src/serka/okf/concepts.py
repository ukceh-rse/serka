"""Builds OKF concepts from the ingest pipeline's EIDC records, extracted nodes and relations, and
Legilo supporting documents, plus the generated `ontology/` concepts and the index files."""

import mimetypes
import re
from dataclasses import dataclass
from typing import Any, Iterable

import yaml
from haystack import Document

from serka import ontology
from serka.okf import ids

OKF_VERSION = "0.2"
_DESCRIPTION_CHARS = 300


@dataclass
class Concept:
	"""One bundle file: `id` is its path without `.md`."""

	id: str
	meta: dict[str, Any]
	body: str = ""

	def render(self) -> str:
		front = yaml.safe_dump(self.meta, sort_keys=False, allow_unicode=True, width=1_000_000)
		text = f"---\n{front}---\n"
		return f"{text}\n{self.body.strip()}\n" if self.body.strip() else text


def _escape(text: str) -> str:
	"""Link text with brackets escaped, on one line."""
	return " ".join(text.split()).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _link(text: str, target: str) -> str:
	return f"[{_escape(text)}]({target})"


def _humanise(name: str) -> str:
	"""`pointOfContact` -> "point of contact", `data-curator` -> "data curator"."""
	return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).replace("-", " ").lower()


def _summary(text: str) -> str:
	"""A one-paragraph description: the text up to the last sentence end within the limit."""
	text = " ".join(text.split())
	if len(text) <= _DESCRIPTION_CHARS:
		return text
	cut = text[:_DESCRIPTION_CHARS]
	end = cut.rfind(". ")
	return cut[: end + 1] if end > 0 else cut.rstrip() + "…"


def _local_name(curie: str) -> str:
	prefix, sep, local = curie.partition(":")
	if sep and prefix in ontology.PREFIXES:
		return local
	return re.split(r"[#/]", curie.rstrip("/#"))[-1]


def _section(heading: str, lines: list[str], intro: str | None = None) -> str:
	if not lines:
		return ""
	parts = [f"## {heading}"]
	if intro:
		parts.append(intro)
	parts.append("\n".join(lines))
	return "\n\n".join(parts)


def _body(*sections: str) -> str:
	return "\n\n".join(s for s in sections if s)


class Vocabulary:
	"""Links roles and predicates to their ontology concepts, recording which ones are used."""

	def __init__(self) -> None:
		self.types: dict[str, str] = {}  # DOO type CURIE -> OKF type
		self.roles: dict[str, set[str]] = {}  # role individual CURIE -> EIDC role names
		self.predicates: set[str] = set()

	def use_type(self, okf_type: str, curie: str) -> None:
		self.types[curie] = okf_type

	def role(self, role: str) -> str:
		curie = ontology.ROLES.get(role, ontology.DEFAULT_ROLE)
		self.roles.setdefault(curie, set()).add(role)
		return _link(_humanise(role), f"/ontology/roles/{_local_name(curie)}")

	def predicate(self, curie: str, text: str | None = None) -> str:
		self.predicates.add(curie)
		name = _local_name(curie)
		return _link(text or _humanise(name), f"/ontology/predicates/{name}")


def _tags(record: dict[str, Any]) -> list[str]:
	"""Keyword values without a vocabulary URI; those with one become theme concepts."""
	tags: dict[str, None] = {}
	for field, values in record.items():
		if field.startswith("keywords") and isinstance(values, list):
			for kw in values:
				if isinstance(kw, dict) and kw.get("value") and not kw.get("uri"):
					tags[kw["value"]] = None
	return list(tags)


def _ancestors(theme_uris: Iterable[str], broader: dict[str, set[str]]) -> set[str]:
	seen: set[str] = set()
	stack = list(theme_uris)
	while stack:
		uri = stack.pop()
		if uri in seen:
			continue
		seen.add(uri)
		stack.extend(broader.get(uri, ()))
	return seen


def _bbox(node: dict[str, Any]) -> dict[str, float] | None:
	keys = {"north": "north_boundary", "south": "south_boundary", "east": "east_boundary", "west": "west_boundary"}
	if not all(k in node for k in keys.values()):
		return None
	return {name: float(node[key]) for name, key in keys.items()}


class _Catalogue:
	"""Indexes the extractor output for rendering."""

	def __init__(
		self,
		records: list[dict[str, Any]],
		nodes: dict[str, list[dict[str, Any]]],
		relationships: dict[str, list[tuple[Any, ...]]],
	) -> None:
		self.records = {r.get("uri", ""): r for r in records}
		self.datasets = {n["uri"]: n for n in nodes.get("Dataset", []) if n.get("uri")}
		self.people = {n["uri"]: n for n in nodes.get("Person", [])}
		self.funders = {n["uri"]: n for n in nodes.get("FundingAgency", [])}
		self.orgs = {**self.funders, **{n["uri"]: n for n in nodes.get("Organisation", [])}}
		self.themes = {n["uri"]: n for n in nodes.get("Concept", [])}
		self.citations = {n["uri"]: n for n in nodes.get("Document", [])}
		self.grants = {n["uri"]: n for n in nodes.get("Grant", [])}

		self.roles: dict[str, dict[str, list[str]]] = {}  # dataset -> agent -> roles
		for dataset, agent, role in relationships.get("ASSOCIATED_WITH", []):
			self.roles.setdefault(dataset, {}).setdefault(agent, []).append(role)
		self.affiliations: dict[str, list[str]] = {}
		for person, org in sorted(relationships.get("AFFILIATED_WITH", [])):
			self.affiliations.setdefault(person, []).append(org)
		self.dataset_themes: dict[str, list[str]] = {}
		for dataset, theme in sorted(relationships.get("HAS_THEME", [])):
			self.dataset_themes.setdefault(dataset, []).append(theme)
		self.broader: dict[str, set[str]] = {}
		for child, parent in relationships.get("BROADER", []):
			self.broader.setdefault(child, set()).add(parent)
		self.relations: dict[str, list[tuple[str, str]]] = {}  # source -> (predicate, target)
		for source, predicate, target in relationships.get("RELATION", []):
			self.relations.setdefault(source, []).append((predicate, target))

	def agent(self, uri: str) -> tuple[str, str]:
		"""(concept ID, name) for a person or organisation."""
		if uri in self.people:
			return ids.person_id(uri), self.people[uri].get("name") or uri
		return ids.organisation_id(uri), self.orgs.get(uri, {}).get("name") or uri

	def dataset_link(self, uri: str) -> str:
		"""A link to the dataset's concept when it is in the bundle, else to the catalogue."""
		if uri in self.datasets:
			return _link(self.datasets[uri].get("title") or uri, f"/{ids.dataset_id(uri)}")
		return _link(ids.dataset_id(uri).split("/", 1)[1], uri)

	def grant_title(self, uri: str) -> str:
		grant = self.grants.get(uri, {})
		return grant.get("title") or f"Grant {grant.get('grant_number', uri)}"


def _dataset(cat: _Catalogue, vocab: Vocabulary, node: dict[str, Any], docs: list[Concept]) -> Concept:
	uri = node["uri"]
	record = cat.records.get(uri, {})
	description = record.get("description") or ""
	meta: dict[str, Any] = {"type": "dataset", "title": node.get("title") or uri}
	if description:
		meta["description"] = _summary(description)
	meta["resource"] = uri
	if tags := _tags(record):
		meta["tags"] = tags
	if published := node.get("publication_date"):
		meta["published"] = str(published)[:10]
	if "citations" in node:
		meta["citations"] = int(node["citations"])
	if bbox := _bbox(node):
		meta["bbox"] = bbox
	direct_themes = cat.dataset_themes.get(uri, [])
	if direct_themes:
		meta["themes"] = sorted(ids.theme_id(t) for t in _ancestors(direct_themes, cat.broader))
	for key in ("licence", "access_rights"):
		if node.get(key):
			meta[key] = node[key]
	temporal = {k: node[f"temporal_{k}"] for k in ("start", "end") if node.get(f"temporal_{k}")}
	if temporal:
		meta["temporal"] = temporal
	if node.get("identifiers"):
		meta["identifiers"] = node["identifiers"]

	contributors, contributor_keys = [], []
	for agent, roles in cat.roles.get(uri, {}).items():
		agent_id, name = cat.agent(agent)
		role_links = ", ".join(vocab.role(r) for r in dict.fromkeys(roles))
		contributors.append(f"- {_link(name, '/' + agent_id)} — {role_links}")
		role_names = dict.fromkeys(_local_name(ontology.ROLES.get(r, ontology.DEFAULT_ROLE)) for r in roles)
		contributor_keys.append({"id": agent_id, "roles": list(role_names)})

	related, grants, cited_by = [], [], []
	grant_ids: dict[str, None] = {}
	funder_ids: dict[str, None] = {}
	for predicate, target in cat.relations.get(uri, []):
		if predicate == "dcterms:isReferencedBy":
			text = cat.citations.get(target, {}).get("bibliographic_citation") or target
			cited_by.append(f"- {_link(text, target)}")
		elif predicate == "doo:originatingGrant":
			funders = [s for s, rels in cat.relations.items() if ("frapo:awards", target) in rels]
			funded_by = "".join(f", from {_link(cat.agent(f)[1], '/' + ids.organisation_id(f))}" for f in funders)
			grants.append(f"- {_link(cat.grant_title(target), '/' + ids.grant_id(target))}{funded_by}")
			grant_ids[ids.grant_id(target)] = None
			funder_ids.update(dict.fromkeys(ids.organisation_id(f) for f in funders))
		else:
			related.append(f"- {vocab.predicate(predicate)}: {cat.dataset_link(target)}")

	# Repeat the body's relations in a form the loader reads without parsing prose
	if contributor_keys:
		meta["contributors"] = contributor_keys
	if grant_ids:
		meta["grants"] = list(grant_ids)
	if funder_ids:
		meta["funders"] = list(funder_ids)

	theme_lines = [
		f"- {_link(cat.themes.get(t, {}).get('label') or t, '/' + ids.theme_id(t))}" for t in direct_themes
	]
	doc_lines = [f"- {_link(d.meta['title'], '/' + d.id)}" for d in docs]

	body = _body(
		_section("Description", [description.strip()] if description.strip() else []),
		_section("Lineage", [record["lineage"].strip()] if (record.get("lineage") or "").strip() else []),
		_section("Contributors", contributors),
		_section("Themes", theme_lines, f"Themes of this dataset ({vocab.predicate('dcat:theme')}):" if theme_lines else None),
		_section("Related", related),
		_section("Funding", grants, f"Funded by ({vocab.predicate('doo:originatingGrant')}):" if grants else None),
		_section(
			"Supporting documents",
			doc_lines,
			f"Supporting documents of this dataset ({vocab.predicate('dcterms:references')}):" if doc_lines else None,
		),
		_section(
			"Cited by",
			cited_by,
			f"Publications that cite this dataset ({vocab.predicate('dcterms:isReferencedBy')}):" if cited_by else None,
		),
	)
	return Concept(ids.dataset_id(uri), meta, body)


def _document(cat: _Catalogue, doc: Document) -> Concept:
	dataset_uri = doc.meta.get("uri", "")
	filename = doc.meta.get("filename") or ""
	media_type, _ = mimetypes.guess_type(filename)
	meta: dict[str, Any] = {
		"type": "document",
		"title": filename or "Supporting document",
		"media_type": media_type or "application/octet-stream",
	}
	backlink = f"Supporting document of {cat.dataset_link(dataset_uri)}."
	return Concept(ids.document_id(dataset_uri, doc.id), meta, _body(backlink, (doc.content or "").strip()))


def _person(cat: _Catalogue, vocab: Vocabulary, uri: str) -> Concept:
	person = cat.people[uri]
	meta = {"type": "person", "title": person.get("name") or uri, "resource": uri}
	lines = [
		f"- {vocab.predicate('org:memberOf')}: {_link(cat.agent(org)[1], '/' + ids.organisation_id(org))}"
		for org in cat.affiliations.get(uri, [])
	]
	return Concept(ids.person_id(uri), meta, _section("Affiliations", lines))


def _organisation(cat: _Catalogue, uri: str) -> Concept:
	meta: dict[str, Any] = {"type": "organisation", "title": cat.orgs[uri].get("name") or uri, "resource": uri}
	if uri in cat.funders:
		meta["tags"] = ["funder"]
	return Concept(ids.organisation_id(uri), meta)


def _grant(cat: _Catalogue, vocab: Vocabulary, uri: str) -> Concept:
	grant = cat.grants[uri]
	meta: dict[str, Any] = {"type": "grant", "title": cat.grant_title(uri)}
	if see_also := grant.get("see_also"):
		meta["resource"] = see_also
	if number := grant.get("grant_number"):
		meta["grant_number"] = number
	funders = [s for s, rels in cat.relations.items() if ("frapo:awards", uri) in rels]
	lines = [
		f"- {vocab.predicate('frapo:awards', 'awarded by')}: {_link(cat.agent(f)[1], '/' + ids.organisation_id(f))}"
		for f in funders
	]
	return Concept(ids.grant_id(uri), meta, _section("Funding", lines))


def _theme(cat: _Catalogue, vocab: Vocabulary, uri: str) -> Concept:
	theme = cat.themes[uri]
	meta: dict[str, Any] = {"type": "theme", "title": theme.get("label") or uri, "resource": uri}
	if scheme := theme.get("scheme"):
		meta["tags"] = [scheme]
	lines = [
		f"- {vocab.predicate('skos:broader')}: {_link(cat.themes.get(p, {}).get('label') or p, '/' + ids.theme_id(p))}"
		for p in sorted(cat.broader.get(uri, ()))
	]
	return Concept(ids.theme_id(uri), meta, _section("Broader themes", lines))


def _expand(curie: str) -> str:
	prefix, sep, local = curie.partition(":")
	return ontology.PREFIXES[prefix] + local if sep and prefix in ontology.PREFIXES else curie


def _ontology_concept(kind: str, curie: str, description: str, body_lines: list[str]) -> Concept:
	meta: dict[str, Any] = {"type": "ontology", "title": _local_name(curie)}
	if description:
		meta["description"] = description
	meta["resource"] = _expand(curie)
	meta["tags"] = [kind]
	body = "\n\n".join([f"DOO identifier: `{curie}`.", *body_lines])
	return Concept(f"ontology/{kind}s/{_local_name(curie)}", meta, body)


def ontology_concepts(vocab: Vocabulary) -> list[Concept]:
	"""One concept for each type, role and predicate the bundle uses."""
	defs = ontology.DEFINITIONS
	concepts = [
		_ontology_concept("type", curie, defs.get(curie, ""), [f"Concepts of OKF type `{okf_type}` have this type."])
		for curie, okf_type in sorted(vocab.types.items())
	]
	for curie, eidc_roles in sorted(vocab.roles.items()):
		role_class = ontology.ROLE_CLASSES.get(curie, "")
		class_name = _humanise(_local_name(role_class).removesuffix("Role")) if role_class else ""
		lines = [f"A kind of {class_name} role (`{role_class}`)." if role_class else ""]
		names = ", ".join(f'"{_humanise(r)}"' for r in sorted(eidc_roles))
		lines.append(f"Used for the EIDC contributor roles {names}.")
		description = f"The {_humanise(_local_name(curie))} role ({names}). {defs.get(role_class, '')}".strip()
		concepts.append(_ontology_concept("role", curie, description, [line for line in lines if line]))
	for curie in sorted(vocab.predicates):
		concepts.append(_ontology_concept("predicate", curie, defs.get(curie, ""), []))
	return concepts


_DIRECTORIES = {
	"datasets": ("Datasets", "EIDC datasets; each links its supporting documents under its own directory."),
	"people": ("People", "People who contributed to datasets, identified by ORCID where known."),
	"organisations": ("Organisations", "Organisations that contributed to or funded datasets; funders are tagged `funder`."),
	"grants": ("Grants", "Grants that funded the work producing datasets."),
	"themes": ("Themes", "Themes and keywords from controlled vocabularies, with links to broader themes."),
	"ontology": ("Ontology", "The meaning of the bundle's concept types, contributor roles and relation predicates."),
}


def _index_line(concept: Concept) -> str:
	tags = concept.meta.get("tags")
	fallback = concept.meta["type"].capitalize() + (f" ({', '.join(tags)})" if tags else "")
	summary = concept.meta.get("description") or fallback
	return f"- {_link(concept.meta['title'], '/' + concept.id)} — {_escape(_summary(summary))}"


def index_files(concepts: list[Concept]) -> dict[str, str]:
	"""`index.md` at the root and in each top-level directory, keyed by bundle-relative path."""
	by_dir: dict[str, list[Concept]] = {}
	for c in concepts:
		top = c.id.split("/", 1)[0]
		# Supporting documents are linked from their dataset, not listed in the index
		if top == "datasets" and "/docs/" in c.id:
			continue
		by_dir.setdefault(top, []).append(c)

	root = [f'---\nokf_version: "{OKF_VERSION}"\n---\n', "# EIDC catalogue\n"]
	files: dict[str, str] = {}
	for top, (title, description) in _DIRECTORIES.items():
		members = by_dir.get(top)
		if not members:
			continue
		root.append(f"- [{title}](/{top}/index) — {description}")
		if top == "ontology":
			sections = []
			for kind, heading in (("types", "Types"), ("roles", "Roles"), ("predicates", "Predicates")):
				group = sorted((c for c in members if c.id.startswith(f"ontology/{kind}/")), key=lambda c: c.id)
				if group:
					sections.append(f"## {heading}\n\n" + "\n".join(_index_line(c) for c in group))
			files["ontology/index.md"] = f"# {title}\n\n{description}\n\n" + "\n\n".join(sections) + "\n"
		else:
			lines = "\n".join(_index_line(c) for c in sorted(members, key=lambda c: (c.meta["title"].lower(), c.id)))
			files[f"{top}/index.md"] = f"# {title}\n\n{description}\n\n{lines}\n"
	files["index.md"] = "\n".join(root) + "\n"
	return files


_TYPE_CURIES = {
	"dataset": "Dataset",
	"person": "Person",
	"organisation": "Organisation",
	"grant": "Grant",
	"theme": "Concept",
	"document": "DigitalManifestation",
}


def build_concepts(
	records: list[dict[str, Any]],
	nodes: dict[str, list[dict[str, Any]]],
	relationships: dict[str, list[tuple[Any, ...]]],
	documents: list[Document],
) -> list[Concept]:
	"""Every concept of the bundle, including the ontology concepts for the terms used."""
	cat = _Catalogue(records, nodes, relationships)
	vocab = Vocabulary()

	docs_by_dataset: dict[str, list[Concept]] = {}
	for doc in documents:
		if doc.meta.get("uri") in cat.datasets:
			concept = _document(cat, doc)
			docs_by_dataset.setdefault(doc.meta["uri"], []).append(concept)

	concepts = [_dataset(cat, vocab, n, docs_by_dataset.get(uri, [])) for uri, n in cat.datasets.items()]
	concepts += [c for group in docs_by_dataset.values() for c in group]
	concepts += [_person(cat, vocab, uri) for uri in cat.people]
	concepts += [_organisation(cat, uri) for uri in cat.orgs]
	concepts += [_grant(cat, vocab, uri) for uri in cat.grants]
	concepts += [_theme(cat, vocab, uri) for uri in cat.themes]

	for okf_type in sorted({c.meta["type"] for c in concepts}):
		vocab.use_type(okf_type, ontology.NODE_TYPES[_TYPE_CURIES[okf_type]])
	if cat.funders:
		vocab.use_type("organisation", ontology.NODE_TYPES["FundingAgency"])
	return concepts + ontology_concepts(vocab)
