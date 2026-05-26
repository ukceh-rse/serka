from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from serka.feedback import FeedbackLogger
from serka.models import Result
from serka.routers.dependencies import get_feedback_logger

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FeedbackPayload(BaseModel):
	model_config = ConfigDict(extra="forbid")

	query: str = Field(..., max_length=2000)
	type: str = Field(..., max_length=100)
	feedback: Optional[str] = Field(None, max_length=500)


@router.post("/submit", summary="Log feedback")
def log_feedback(
	payload: FeedbackPayload,
	feedback_logger: FeedbackLogger = Depends(get_feedback_logger),
) -> Result:
	feedback_logger.log_feedback(payload.model_dump(exclude_none=True))
	return Result(success=True, msg="Feedback logged")
