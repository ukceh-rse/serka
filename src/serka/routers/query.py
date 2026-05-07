from fastapi import APIRouter, Depends, Query

from serka.feedback import FeedbackLogger
from serka.routers.dependencies import get_feedback_logger, get_mcp_search

router = APIRouter(prefix="/query", tags=["Query"])


@router.get("/semantic", summary="Perform a semantic search in the graph database")
async def semantic_graph_search(
	q: str = Query(
		description="Query to perform the semantic search with.",
		examples=["Are there any pike in Windermere lake?"],
	),
	mcp_search=Depends(get_mcp_search),
	feedback_logger: FeedbackLogger = Depends(get_feedback_logger),
) -> list:
	feedback_logger.log_feedback({"query": q, "type": "semantic_search"})
	return await mcp_search(q)
