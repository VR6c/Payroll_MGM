import json
from pathlib import Path
from decimal import Decimal
from functools import lru_cache

@lru_cache(maxsize=1)
def load_rules():
    path = Path(__file__).parent / 'business_rules.json'
    with open(path) as f:
        return json.load(f)

def get_rule(section, key, default=None):
    rules = load_rules()
    value = rules.get(section, {}).get(key, default)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception:
            pass
    return value
