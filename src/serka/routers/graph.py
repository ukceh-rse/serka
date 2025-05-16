from fastapi import Depends, APIRouter
from serka.routers.dependencies import get_dao
from serka.models import Result
from serka.dao import DAO


router = APIRouter(prefix="/graph", tags=["Graph"])


@router.get("/build", summary="Build a graph from the EIDC metadata")
def build(dao: DAO = Depends(get_dao)) -> Result:
	return dao.build_eidc_graph()
