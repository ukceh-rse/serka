from fastapi import Query, Depends, APIRouter
from serka.routers.dependencies import get_dao
from serka.models import GroupedDocuments, Result
from typing import List
from serka.dao import DAO
from serka.feedback import FeedbackLogger
from serka.routers.dependencies import get_config, get_feedback_logger
from serka.models import Config, RAGResponse


router = APIRouter(prefix="/query", tags=["Query"])


@router.get("/semantic", summary="Perform a semantic search in the vector database")
def semantic_search(
	q: str = Query(
		description="Query to perform the semantic search with.",
		examples=["Are there any pike in Windermere lake?"],
	),
	collection: str = Query(
		description="The name of the collection to query in the vector database.",
		default="eidc",
	),
	n: int = Query(
		description="Number of results to return.",
		default=20,
	),
	dao: DAO = Depends(get_dao),
	feedback_loggger: FeedbackLogger = Depends(get_feedback_logger),
) -> List[GroupedDocuments]:
	feedback_loggger.log_feedback(
		{"query": q, "collection": collection, "type": "semantic_search"}
	)
	return dao.query(collection, q, n)


@router.get("/rag", summary="Perform a RAG query")
def rag(
	q: str = Query(
		description="Query to hand the RAG pipeline",
		examples=["Are there any pike in Windermere lake?"],
	),
	collection: str = Query(
		description="The name of the collection to query in the vector database.",
		default="eidc",
	),
	dao: DAO = Depends(get_dao),
	config: Config = Depends(get_config),
	feedback_loggger: FeedbackLogger = Depends(get_feedback_logger),
) -> RAGResponse:
	if config.rag_enabled is False:
		return RAGResponse(
			result=Result(
				success=False,
				msg="Generative answering is currently disabled. Please enable via `config.yaml`",
			),
			answer="",
			query=q,
		)
	collection_desc = config.collections.get(
		collection,
		{
			"description": "No information about the original source of the documents is known."
		},
	)
	feedback_loggger.log_feedback(
		{"query": q, "collection": collection, "type": "rag_query"}
	)
	return dao.rag_query(collection, str(collection_desc), q)
