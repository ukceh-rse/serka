"""Helpers for decoding chat SSE streams in tests."""

import json
from collections.abc import Iterable
from typing import Any


def decode(chunks: Iterable[str | bytes]) -> list[dict[str, Any]]:
	"""Decodes SSE chunks into the JSON payload of every `data:` line, in order."""
	text = "".join(c.decode() if isinstance(c, bytes) else c for c in chunks)
	return [json.loads(line[len("data: ") :]) for line in text.splitlines() if line.startswith("data: ")]


def drain(queue: Any) -> list[dict[str, Any]]:
	"""Decodes everything currently in an Emitter queue (sentinel excluded)."""
	items: list[str] = []
	while not queue.empty():
		item = queue.get_nowait()
		if item is not None:
			items.append(item)
	return decode(items)


def types(events: list[dict[str, Any]]) -> list[str]:
	return [e["type"] for e in events]


def customs(events: list[dict[str, Any]], name: str) -> list[Any]:
	return [e["value"] for e in events if e["type"] == "CUSTOM" and e["name"] == name]


def steps(events: list[dict[str, Any]]) -> list[str]:
	return [e["stepName"] for e in events if e["type"] == "STEP_STARTED"]


def answer_text(events: list[dict[str, Any]]) -> str:
	return "".join(e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT")
