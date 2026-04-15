from datetime import datetime
from typing import Any, Dict, List

from pymongo import MongoClient


class FeedbackLogger:
	def __init__(self, host: str, port: int):
		self.client = MongoClient(host, port)
		self.db = self.client.serka
		self.collection = self.db.feedback

	def log_feedback(self, feedback: Dict[str, Any]) -> None:
		feedback["timestamp"] = datetime.now()
		self.collection.insert_one(feedback)

	def get_feedback(self) -> List[Dict[str, Any]]:
		return list(self.collection.find({}, {"_id": 0}))
