"""Reads an OKF bundle from disk: frontmatter, body and outgoing bundle-relative links."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

RESERVED = ("index.md", "log.md")
# A markdown link's target; link text may contain escaped brackets
_LINK = re.compile(r"\[(?:\\.|[^\]\\])*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


@dataclass
class BundleFile:
	"""One `.md` file. `id` is its bundle path without `.md` (e.g. `people/x`, `ontology/index`)."""

	id: str
	raw: str
	meta: dict[str, Any]
	body: str
	links: list[str] = field(default_factory=list)

	@property
	def is_concept(self) -> bool:
		return f"{self.id.rsplit('/', 1)[-1]}.md" not in RESERVED and bool(self.meta.get("type"))


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
	if not text.startswith("---\n"):
		return {}, text
	end = text.find("\n---", 4)
	if end < 0:
		return {}, text
	meta = yaml.safe_load(text[4:end]) or {}
	body = text[end + 4 :].lstrip("\n")
	return (meta if isinstance(meta, dict) else {}), body


def normalise_id(target: str) -> str | None:
	"""A bundle-relative link target as a concept ID, or None for external links.
	`/people/x`, `people/x`, `/people/x.md` and `/people/x#part` all give `people/x`."""
	target = target.strip()
	if not target or target.startswith("#") or _SCHEME.match(target):
		return None
	target = target.split("#", 1)[0].split("?", 1)[0].strip("/")
	target = target.removesuffix(".md")
	return target or None


def outgoing_links(body: str, known: set[str]) -> list[str]:
	"""Concept IDs this body links to, in first-seen order. Links to unknown IDs are dropped."""
	links: dict[str, None] = {}
	for target in _LINK.findall(body):
		concept_id = normalise_id(target)
		if concept_id is None:
			continue
		if concept_id not in known:
			logger.debug("Broken bundle link to %s", target)
			continue
		links[concept_id] = None
	return list(links)


def read_bundle(root: Path) -> list[BundleFile]:
	"""Every `.md` file of the bundle, with links resolved against the bundle's own files."""
	files = []
	for path in sorted(root.rglob("*.md")):
		raw = path.read_text(encoding="utf-8")
		try:
			meta, body = split_frontmatter(raw)
		except yaml.YAMLError as e:
			logger.warning("Skipping %s: unparseable frontmatter (%s)", path, e)
			continue
		files.append(BundleFile(path.relative_to(root).as_posix().removesuffix(".md"), raw, meta, body))
	known = {f.id for f in files}
	for f in files:
		f.links = [link for link in outgoing_links(f.body, known) if link != f.id]
	return files
