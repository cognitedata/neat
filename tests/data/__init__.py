from pathlib import Path

import yaml
from cognite.client import data_modeling as dm

DATA_DIR = Path(__file__).parent


CAPACITY_MARKET_JSON = DATA_DIR / "970_0ca0c919-046a-4940-b191-f5cc4d0e6513.json"
POWER_GRID_JSON = DATA_DIR / "power-grid-example.json"

_OSDUWElls = DATA_DIR / "IntegrationTestsImmutable-OSDUWells-1.yaml"
_SCENARIO_INSTANCE = DATA_DIR / "IntegrationTestsImmutable-ScenarioInstance-1.yaml"

OSDUWELLS_MODEL: dm.DataModel[dm.View] = dm.DataModel.load(yaml.safe_load(_OSDUWElls.read_text())[0])
SCENARIO_INSTANCE_MODEL: dm.DataModel[dm.View] = dm.DataModel.load(yaml.safe_load(_SCENARIO_INSTANCE.read_text())[0])
