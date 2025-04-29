from fastapi import Query, Depends, APIRouter
from serka.routers.dependencies import get_dao, get_config
from serka.models import Document, Result
from typing import List
from serka.dao import DAO


router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("/list", summary="List collections in the vector database")
def list(dao: DAO = Depends(get_dao)) -> List[str]:
	return dao.list_collections()


@router.get("/peek", summary="Peek into a collection in the vector database")
def peek(
	collection: str = Query(
		description="Name of the collection to peek.",
		default="eidc",
	),
	dao: DAO = Depends(get_dao),
) -> List[Document]:
	return dao.peek(collection)


@router.delete("/delete", summary="Delete a collection in the vector database")
def delete(
	collection: str = Query(
		description="The name of the collection to delete in the vector database.",
	),
	dao: DAO = Depends(get_dao),
) -> Result:
	return dao.delete(collection)


@router.post("/insert", summary="Insert a document into the vector database")
def insert(
	document: Document,
	collection: str = Query(default="eidc"),
	dao: DAO = Depends(get_dao),
) -> Result:
	return dao.insert(document, collection, get_config().unified_metadata)
