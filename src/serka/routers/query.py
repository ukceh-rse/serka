from enum import StrEnum

from fastapi import APIRouter, Depends, Query

from serka.feedback import FeedbackLogger
from serka.routers.dependencies import get_feedback_logger, get_mcp_search

router = APIRouter(prefix="/query", tags=["Query"])


class ReturnType(StrEnum):
	Dataset = "Dataset"
	Person = "Person"
	Organisation = "Organisation"
	Concept = "Concept"
	Document = "Document"


@router.get("/semantic", summary="Perform a semantic search in the graph database")
async def semantic_graph_search(
	q: str = Query(
		description="Query to perform the semantic search with.",
		examples=["Are there any pike in Windermere lake?"],
	),
	return_type: ReturnType | None = Query(
		None, description="DOO type to return; omit for any matched node."
	),
	hops: int = Query(1, ge=0, le=5, description="Max relationship hops from match to return_type."),
	location: str | None = Query(None, description="UK place name to geographically filter datasets."),
	published_after: str | None = Query(None, description="ISO date (YYYY-MM-DD); exclude older datasets."),
	published_before: str | None = Query(None, description="ISO date (YYYY-MM-DD); exclude newer datasets."),
	mcp_search=Depends(get_mcp_search),
	feedback_logger: FeedbackLogger = Depends(get_feedback_logger),
) -> list:
	feedback_logger.log_feedback({
		"query": q,
		"type": "semantic_search",
		"return_type": return_type,
		"hops": hops,
		"location": location,
		"published_after": published_after,
		"published_before": published_before,
	})
	return await mcp_search(
		q,
		return_type=return_type,
		hops=hops,
		location=location,
		published_after=published_after,
		published_before=published_before,
	)
