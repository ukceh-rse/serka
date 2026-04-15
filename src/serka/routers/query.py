from typing import List

from fastapi import APIRouter, Depends, Query

from serka.dao import DAO
from serka.feedback import FeedbackLogger
from serka.models import GroupedDocuments
from serka.routers.dependencies import get_dao, get_feedback_logger

router = APIRouter(prefix="/query", tags=["Query"])


@router.get("/semantic", summary="Perform a semantic search in the graph database")
def semantic_graph_search(
	q: str = Query(
		description="Query to perform the semantic search with.",
		examples=["Are there any pike in Windermere lake?"],
	),
	dao: DAO = Depends(get_dao),
	feedback_logger: FeedbackLogger = Depends(get_feedback_logger),
) -> List[GroupedDocuments]:
	feedback_logger.log_feedback({"query": q, "type": "semantic_search"})
	return dao.query(q)
