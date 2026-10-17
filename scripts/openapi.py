"""Export the current API contract for frontend tooling."""

import json
from pathlib import Path

from app.main import create_app

if __name__ == "__main__":
    target = Path("docs/openapi.json")
    target.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n")
    print(str(target))
