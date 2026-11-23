import sys
from pathlib import Path

GENERATOR = Path(__file__).resolve().parents[1]
# the generator's modules import each other as top-level modules
sys.path.insert(0, str(GENERATOR))

GRAMMAR = GENERATOR / "grammar.tx"
BASE = GENERATOR / "base.wfl"
MODELS = GENERATOR / "WaffleTestingModels"
FILL_DB = GENERATOR.parents[1] / "Resources" / "tests" / "db" / "fill_db"
