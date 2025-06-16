from fastapi import Depends, APIRouter, Query
from serka.routers.dependencies import get_dao
from serka.models import Result
from serka.dao import DAO


router = APIRouter(prefix="/graph", tags=["Graph"])


@router.get("/build", summary="Build a graph from the EIDC metadata")
def build(
	dao: DAO = Depends(get_dao),
	n: int = Query(
		default=10,
		alias="rows",
		ge=1,
		le=10000,
		description="Number of records to fetch from the EIDC catalogue.",
	),
) -> Result:
	return dao.build_eidc_graph(n)
