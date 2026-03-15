"""Unit tests for performance validators."""

from typing import Literal

import pytest

from cognite.neat._config import AlphaFlagConfig, internal_profiles
from cognite.neat._data_model.deployer.data_classes import ChangedField
from cognite.neat._data_model.models.dms._indexes import BtreeIndex
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.rules.dms._orchestrator import DmsDataModelRulesOrchestrator
from cognite.neat._data_model.rules.dms._performance import MissingReverseDirectRelationTargetIndex
from tests.data import SNAPSHOT_CATALOG


@pytest.mark.parametrize("profile", ["deep-additive", "legacy-additive"])
def test_missing_reverse_direct_relation_target_index(
    profile: Literal["deep-additive", "legacy-additive"],
) -> None:
    """Verifies MissingReverseDirectRelationTargetIndex produces issues when run via the orchestrator."""
    config = internal_profiles()[profile]
    mode = config.modeling.mode

    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        "bi_directional_connections", "for_validators", modus_operandi=mode, include_cdm=False, format="snapshots"
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

    on_success = DmsDataModelRulesOrchestrator(
        cdf_snapshot=cdf_snapshot,
        limits=SchemaLimits(),
        modus_operandi=mode,
        can_run_validator=config.validation.can_run_validator,
        alpha_flags=AlphaFlagConfig(enable_experimental_validators=True),
    )
    on_success.run(data_model)
    by_code = on_success.issues.by_code()

    assert MissingReverseDirectRelationTargetIndex.code in by_code


def test_fix_updates_existing_non_cursorable_index() -> None:
    """When a non-cursorable BtreeIndex already exists, the fix should update it rather than add a new one."""
    resources = SNAPSHOT_CATALOG.load_scenario(
        "bi_directional_connections",
        "for_validators",
        modus_operandi="additive",
        include_cdm=False,
    )
    validator = MissingReverseDirectRelationTargetIndex(resources)

    fixes = validator.fix()
    update_fixes = [f for f in fixes if any("nonCursorableIdx" in c.field_path for c in f.changes)]
    assert len(update_fixes) == 1, "Should produce exactly one fix that updates the existing non-cursorable index"

    change = update_fixes[0].changes[0]
    assert isinstance(change, ChangedField), "Should update existing index, not add a new one"
    assert isinstance(change.new_value, BtreeIndex)
    assert change.new_value.cursorable is True
