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

CAPACITY_BID_MODEL: dm.DataModelApply = dm.DataModelApply.load(
    yaml.safe_load((DATA_DIR / "power-CapacityBid-1.yaml").read_text())
)
CAPACITY_BID_CONTAINERS: dm.ContainerApplyList = dm.ContainerApplyList._load(
    yaml.safe_load((DATA_DIR / "power-CapacityBid-containers.yaml").read_text())
)
CAPACITY_BID_JSON = DATA_DIR / "mock_capacity_bid.json"
