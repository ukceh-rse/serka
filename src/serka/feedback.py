import json
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict

_version = version("serka")


class FeedbackLogger:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_feedback(self, feedback: Dict[str, Any]) -> None:
        entry = {**feedback, "timestamp": datetime.now().isoformat(), "version": _version}
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
