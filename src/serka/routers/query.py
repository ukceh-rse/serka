from fastapi import APIRouter, Depends, Query

from serka.feedback import FeedbackLogger
from serka.routers.dependencies import get_feedback_logger, get_mcp_search
from serka.usage import MAX_QUERY_CHARS

router = APIRouter(prefix="/query", tags=["Query"])


@router.get("/semantic", summary="Search the catalogue, returning matching passages with their concepts")
async def semantic_search(
	q: str = Query(
		max_length=MAX_QUERY_CHARS,
		description="Query to perform the search with.",
		examples=["Are there any pike in Windermere lake?"],
	),
	type: str | None = Query(
		None,
		description="OKF concept type to return, e.g. dataset, document, person, organisation, grant, theme; omit for any.",
	),
	location: str | None = Query(None, description="UK place name to geographically filter datasets."),
	published_after: str | None = Query(None, description="ISO date (YYYY-MM-DD); exclude older datasets."),
	published_before: str | None = Query(None, description="ISO date (YYYY-MM-DD); exclude newer datasets."),
	mcp_search=Depends(get_mcp_search),
	feedback_logger: FeedbackLogger = Depends(get_feedback_logger),
) -> list:
	"""The catalogue `search` tool's hits, unchanged: one per matching chunk, each with its concept."""
	feedback_logger.log_feedback({
		"query": q,
		"type": "semantic_search",
		"concept_type": type,
		"location": location,
		"published_after": published_after,
		"published_before": published_before,
	})
	return await mcp_search(
		q,
		type=type,
		location=location,
		published_after=published_after,
		published_before=published_before,
	)
