from fastapi import Depends, APIRouter
from serka.models import Result
from typing import List, Dict, Any
from serka.feedback import FeedbackLogger
from serka.routers.dependencies import get_feedback_logger


router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.get("/list", summary="Get feedback")
def get_feedback(
	feedback_loggger: FeedbackLogger = Depends(get_feedback_logger),
) -> List[Dict[str, Any]]:
	return feedback_loggger.get_feedback()


@router.post("/submit", summary="Log feedback")
def log_feedback(
	feedback: Dict[str, Any],
	feedback_loggger: FeedbackLogger = Depends(get_feedback_logger),
) -> Result:
	feedback_loggger.log_feedback(feedback)
	return Result(success=True, msg="Feedback logged")
