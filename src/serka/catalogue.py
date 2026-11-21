"""Arguments for the MCP catalogue `search` tool, shared by the plain search endpoint and the chat pipeline."""

from typing import Any, Literal

SortBy = Literal["citations", "published"]
Order = Literal["ascending", "descending"]


def search_args(
	query: str | None,
	type: str | None = None,
	published_after: str | None = None,
	published_before: str | None = None,
	sort_by: SortBy | None = None,
	order: Order | None = None,
	limit: int | None = None,
) -> dict[str, Any]:
	"""The `search` tool's arguments, leaving out the ones not set."""
	args: dict[str, Any] = {
		"query": query,
		"type": type,
		"published_after": published_after,
		"published_before": published_before,
		"sort_by": sort_by,
		"order": order,
		"limit": limit,
	}
	return {k: v for k, v in args.items() if v}
