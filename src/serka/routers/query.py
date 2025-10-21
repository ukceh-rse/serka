import uuid
from fastapi import Query, Depends, APIRouter
from serka.routers.dependencies import get_dao
from serka.models import GroupedDocuments, Result
from typing import List, Dict
from serka.dao import DAO
from serka.feedback import FeedbackLogger
from serka.routers.dependencies import get_config, get_feedback_logger
from serka.models import Config, RAGResponse
from fastapi import BackgroundTasks
from fastapi import HTTPException
from serka.jobs import rag_task


router = APIRouter(prefix="/query", tags=["Query"])
answers: Dict[str, RAGResponse] = {}


@router.get("/semantic", summary="Perform a semantic search in the graph database")
def semantic_graph_search(
	q: str = Query(
		description="Query to perform the semantic search with.",
		examples=["Are there any pike in Windermere lake?"],
	),
	dao: DAO = Depends(get_dao),
	feedback_loggger: FeedbackLogger = Depends(get_feedback_logger),
) -> List[GroupedDocuments]:
	feedback_loggger.log_feedback({"query": q, "type": "semantic_search"})
	return dao.query(q)


@router.post("/rag", summary="Submit a graph RAG query asynchronously.")
async def submit_graph_rag(
	background_tasks: BackgroundTasks,
	q: str = Query(
		description="Query to hand the RAG pipeline",
		examples=["Are there any pike in Windermere lake?"],
	),
	hyde: bool = Query(
		default=False,
		description="Whether to generate HyDE (Hypothetical Document Embeddings) for the search.",
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
	id = str(uuid.uuid4())
	answer = RAGResponse(id=id)
	answers[id] = answer
	background_tasks.add_task(rag_task, answer, dao, q)
	return answer


@router.get("/rag", summary="Get the result of a RAG query.")
def get_rag(
	id: str = Query(
		description="The ID of the RAG query to get the result of.",
		examples=["a1b2c3d4"],
	),
) -> RAGResponse:
	if id not in answers:
		raise HTTPException(status_code=404, detail=f"Answer with ID {id} not found")
	return answers[id]
