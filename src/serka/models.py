from pydantic import BaseModel
from typing import List


class Result(BaseModel):
	success: bool
	msg: str


class RAGResponse(BaseModel):
	id: str
	answer: str = ""
	thinking: bool = True
	complete: bool = False
	thinking_tokens: List[str] = []
	tokens: List[str] = []
