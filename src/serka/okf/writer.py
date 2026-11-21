import shutil
import uuid
from pathlib import Path

from serka.okf.concepts import Concept, index_files


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
