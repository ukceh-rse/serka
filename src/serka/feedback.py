import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class FeedbackLogger:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_feedback(self, feedback: Dict[str, Any]) -> None:
        feedback["timestamp"] = datetime.now().isoformat()
        with self.path.open("a") as f:
            f.write(json.dumps(feedback) + "\n")
