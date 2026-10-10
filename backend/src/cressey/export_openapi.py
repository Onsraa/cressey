import json
from pathlib import Path

from cressey.app import create_app
from cressey.settings import Settings

if __name__ == "__main__":
    out = Path(__file__).parents[2] / "openapi.json"
    out.write_text(json.dumps(create_app(Settings(_env_file=None)).openapi(), indent=2))
    print(out)
