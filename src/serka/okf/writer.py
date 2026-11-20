import logging
import shutil
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from haystack import Document, component

from serka.okf.concepts import Concept, build_concepts, index_files

logger = logging.getLogger(__name__)


def write_bundle(target: Path, concepts: list[Concept]) -> None:
	"""Builds the bundle in a temporary sibling directory, then renames it over `target`,
	so a failed run leaves the previous bundle as it was."""
	target = target.resolve()
	target.parent.mkdir(parents=True, exist_ok=True)
	tmp = target.with_name(f"{target.name}.tmp-{uuid.uuid4().hex[:8]}")
	try:
		files = {f"{c.id}.md": c.render() for c in concepts}
		files.update(index_files(concepts))
		for rel_path, text in files.items():
			path = tmp / rel_path
			path.parent.mkdir(parents=True, exist_ok=True)
			path.write_text(text, encoding="utf-8")
		old = target.with_name(f"{target.name}.old-{uuid.uuid4().hex[:8]}")
		if target.exists():
			target.rename(old)
		try:
			tmp.rename(target)
		except BaseException:
			if old.exists():
				old.rename(target)
			raise
		shutil.rmtree(old, ignore_errors=True)
	except BaseException:
		shutil.rmtree(tmp, ignore_errors=True)
		raise


@component
class OKFBundleWriter:
	"""Writes the ingest run's output as an OKF bundle, replacing the previous bundle."""

	def __init__(self, bundle_dir: str):
		self.bundle_dir = bundle_dir

	@component.output_types(bundle_dir=str, concepts=Dict[str, int])
	def run(
		self,
		records: List[Dict[Any, Any]],
		nodes: Dict[str, List[Dict[str, Any]]],
		relationships: Dict[str, List[Tuple]],  # type: ignore[type-arg]  # must match EntityExtractor's output type
		documents: List[Document],
	) -> Dict[str, Any]:
		concepts = build_concepts(records, nodes, relationships, documents)
		write_bundle(Path(self.bundle_dir), concepts)
		counts = dict(Counter(c.meta["type"] for c in concepts))
		logger.info("OKF bundle written to %s: %s", self.bundle_dir, counts)
		return {"bundle_dir": str(Path(self.bundle_dir).resolve()), "concepts": counts}
