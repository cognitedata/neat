import pytest

from cognite.neat import NeatConfig
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation
from cognite.neat._data_model.validation.dms._views import CyclicImplements
from tests.data import SNAPSHOT_CATALOG


@pytest.mark.parametrize("enable", [True, False])
def test_with_test_scoped_alpha_validator(enable: bool) -> None:
    config = NeatConfig.create_predefined()
    config.alpha.enable_experimental_validators = enable
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

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

    assert (CyclicImplements.code in by_code) == enable
