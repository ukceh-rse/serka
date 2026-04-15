from typing import Any, Dict, List

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


@router.get("/list", summary="List logged feedback")
def list_feedback(
	feedback_logger: FeedbackLogger = Depends(get_feedback_logger),
) -> List[Dict[str, Any]]:
	return feedback_logger.get_feedback()
