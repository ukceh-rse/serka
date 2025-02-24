from pymongo import MongoClient
from bson import json_util
from typing import Dict, Any
import json


class FeedbackLogger:
	def __init__(self, host: str, port: int):
		self.client = MongoClient(host, port)
		self.db = self.client.serka
		self.collection = self.db.feedback

	def log_feedback(self, feedback: Dict[str, Any]):
		self.collection.insert_one(feedback)

	def get_feedback(self):
		feedback = [obj for obj in self.collection.find({}, limit=10)]
		json_str = json_util.dumps(feedback)
		return json.loads(json_str)
