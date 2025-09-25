from functools import lru_cache
from pathlib import Path

import yaml

from cognite.neat.v0.core._data_model._shared import ImportedDataModel
from cognite.neat.v0.core._data_model.models.physical import (
    PhysicalDataModel,
    UnverifiedPhysicalDataModel,
)
from cognite.neat.v0.core._issues.errors import NeatValueError

_CLASSIC_TO_CORE_MAPPING = Path(__file__).resolve().parent / "_classic2core.yaml"


@lru_cache(maxsize=1)
def _read_source_file() -> str:
    return _CLASSIC_TO_CORE_MAPPING.read_text()


def load_classic_to_core_mapping(org_name: str | None, source_space: str, source_version: str) -> PhysicalDataModel:
    from cognite.neat.v0.core._data_model.importers import DictImporter
    from cognite.neat.v0.core._data_model.transformers import VerifyPhysicalDataModel

    raw_str = _read_source_file()
    if org_name is not None:
        raw_str = raw_str.replace("Classic", org_name)

    loaded = yaml.safe_load(raw_str)
    loaded["metadata"]["space"] = source_space
    loaded["metadata"]["version"] = source_version

    read: ImportedDataModel[UnverifiedPhysicalDataModel] = DictImporter(loaded).to_data_model()
    if not isinstance(read.unverified_data_model, UnverifiedPhysicalDataModel):
        raise NeatValueError(f"Expected physical data model, but got {type(read.unverified_data_model).__name__}")

    verified = VerifyPhysicalDataModel(validate=False).transform(read)

    return verified
