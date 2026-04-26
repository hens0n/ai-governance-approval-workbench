import json
from functools import lru_cache
from pathlib import Path

_POLICY_DIR = Path(__file__).parent


@lru_cache(maxsize=8)
def load_json(name: str) -> dict:
    return json.loads((_POLICY_DIR / name).read_text())
