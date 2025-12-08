from pathlib import Path

from cognite.neat._data_model.models.dms import DataModelReference

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

ENCODING = "utf-8"
COGNITE_CORE_ID = DataModelReference(space="cdf_cdm", external_id="CogniteCore", version="v1")
COGNITE_CORE_MODEL_YAML = SNAPSHOT_DIR / "cognite_core_model.yaml"
COGNITE_CORE_VIEW_YAML = SNAPSHOT_DIR / "cognite_core_view.yaml"
COGNITE_CORE_CONTAINER_YAML = SNAPSHOT_DIR / "cognite_core_container.yaml"
