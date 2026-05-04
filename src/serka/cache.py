import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

root = Path(".cache")


def _dir(*parts: str) -> Path:
	p = root.joinpath(*parts)
	p.mkdir(parents=True, exist_ok=True)
	return p


def get_embedding(content: str) -> Optional[list[float]]:
	h = hashlib.sha256(content.encode()).hexdigest()
	p = root / "embeddings" / f"{h}.json"
	if p.exists():
		return json.loads(p.read_text())
	return None


def save_embedding(content: str, embedding: list[float]) -> None:
	h = hashlib.sha256(content.encode()).hexdigest()
	(_dir("embeddings") / f"{h}.json").write_text(json.dumps(embedding))
