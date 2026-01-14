from typing import Any

import pytest

from cognite.neat import NeatConfig
from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.validation.dms._base import DataModelValidator  # for identity check
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation
from cognite.neat._data_model.validation.dms._views import CyclicImplements
from cognite.neat._issues import ConsistencyError
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from tests.data import SNAPSHOT_CATALOG


@pytest.mark.parametrize("enable", [True, False])
def test_with_test_scoped_alpha_validator(monkeypatch: Any, enable: bool) -> None:
    config = NeatConfig.create_predefined()
    config.alpha.enable_experimental_validators = enable
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    class AlphaValidatorLocal(DataModelValidator):
        code = "NEAT-ALPHA-001"
        issue_type = ConsistencyError
        alpha = True

        def __init__(self, validation_resources: ValidationResources) -> None:
            self.validation_resources = validation_resources

        def run(self) -> list[ConsistencyError]:
            return [ConsistencyError(message="Testing Alpha Validator", fix="x", code=self.code)]

    def patched_get(
        base_cls: type[DataModelValidator], exclude_direct_abc_inheritance: bool = True
    ) -> list[type[DataModelValidator]]:
        found = get_concrete_subclasses(base_cls, exclude_direct_abc_inheritance)
        # Only modify when caller asks about DataModelValidator
        if base_cls is DataModelValidator:
            return [*found, AlphaValidatorLocal]
        return found

    monkeypatch.setattr(
        "cognite.neat._data_model.validation.dms._orchestrator.get_concrete_subclasses",
        patched_get,
    )

    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        "cyclic_implements", "for_validators", modus_operandi=mode, include_cdm=False, format="snapshots"
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

    on_success = DmsDataModelValidation(
        cdf_snapshot=cdf_snapshot,
        limits=SchemaLimits(),
        modus_operandi=mode,
        can_run_validator=can_run_validator,
        enable_alpha_validators=enable,
    )
    on_success.run(data_model)
    by_code = on_success.issues.by_code()

    assert (AlphaValidatorLocal.code in by_code) == enable
    assert (CyclicImplements.code in by_code) == enable
