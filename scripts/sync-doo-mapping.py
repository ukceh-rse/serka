"""Copy the canonical DOO mapping to the backend and UI.

Each component is built from its own container context, so the file is copied rather
than shared. tests/test_ontology.py fails if the copies drift.

	uv run scripts/sync-doo-mapping.py
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "mcp-server" / "src" / "serka-mcp" / "doo_mapping.json"
COPIES = [ROOT / "src" / "serka" / "doo_mapping.json", ROOT / "ui" / "src" / "doo_mapping.json"]

if __name__ == "__main__":
	for dest in COPIES:
		shutil.copyfile(SOURCE, dest)
		print(f"{SOURCE.relative_to(ROOT)} -> {dest.relative_to(ROOT)}")
