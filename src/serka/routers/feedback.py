from typing import Any, Dict

from fastapi import APIRouter, Depends

from serka.feedback import FeedbackLogger
from serka.models import Result
from serka.routers.dependencies import get_feedback_logger

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("/submit", summary="Log feedback")
def log_feedback(
	feedback: Dict[str, Any],
	feedback_logger: FeedbackLogger = Depends(get_feedback_logger),
) -> Result:
	feedback_logger.log_feedback(feedback)
	return Result(success=True, msg="Feedback logged")
