from cognite.neat import NeatConfig
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import SpaceReference
from cognite.neat._data_model.models.dms._space import SpaceRequest
from cognite.neat._data_model.rules.cdf._orchestrator import CDFRulesOrchestrator
from cognite.neat._data_model.rules.cdf._spaces import EmptySpaces
from tests.data import SNAPSHOT_CATALOG


def test_spaces_rules() -> None:
    config = NeatConfig.create_predefined()
    config.alpha.enable_experimental_validators = True
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    _, cdf = SNAPSHOT_CATALOG.load_scenario(
        "cyclic_implements", "for_validators", modus_operandi=mode, include_cdm=False, format="snapshots"
    )

    cdf.spaces = {SpaceReference(space="empty_as_space"): SpaceRequest(space="empty_as_space")}

    on_success = CDFRulesOrchestrator(
        limits=SchemaLimits(),
        can_run_validator=can_run_validator,
        enable_alpha_validators=config.alpha.enable_experimental_validators,
    )

    on_success.run(cdf_snapshot=cdf)
    by_code = on_success.issues.by_code()

    assert EmptySpaces.code in by_code
    assert len(by_code[EmptySpaces.code]) == 1
