"""Tests for requires constraint validators."""

from typing import Literal

import pytest

from cognite.neat._config import internal_profiles
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.validation.dms._containers import (
    MissingRequiresConstraint,
    RequiresConstraintComplicatesIngestion,
    RequiresConstraintCycle,
    UnnecessaryRequiresConstraint,
)
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation
from tests.data import SNAPSHOT_CATALOG


@pytest.fixture
def validation_result() -> DmsDataModelValidation:
    """Run validation on the requires_constraints scenario and return the result."""
    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        local_scenario_name="requires_constraints",
        cdf_scenario_name="for_validators",
        modus_operandi="additive",
        include_cdm=False,
        format="snapshots",
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)
    validation = DmsDataModelValidation(cdf_snapshot=cdf_snapshot, limits=SchemaLimits(), modus_operandi="additive")
    validation.run(data_model)
    return validation


PROBLEMS = {
    MissingRequiresConstraint: {"AssetContainer", "DescribableContainer", "TransitiveParent", "TagContainer"},
    UnnecessaryRequiresConstraint: {"OrderContainer", "CustomerContainer"},
    RequiresConstraintCycle: {"CycleContainerA", "CycleContainerB"},
    RequiresConstraintComplicatesIngestion: {"IngestionAssetContainer", "IngestionDescribableContainer"},
}


@pytest.mark.parametrize("profile", ["deep-additive", "legacy-additive"])
def test_requires_constraints_validation(
    profile: Literal["deep-additive", "legacy-additive"],
) -> None:
    """Test all requires constraint validators with the requires_constraints scenario."""
    config = internal_profiles()[profile]
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        local_scenario_name="requires_constraints",
        cdf_scenario_name="for_validators",
        modus_operandi=mode,
        include_cdm=False,
        format="snapshots",
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

    on_success = DmsDataModelValidation(
        cdf_snapshot=cdf_snapshot,
        limits=SchemaLimits(),
        modus_operandi=mode,
        can_run_validator=can_run_validator,
    )
    on_success.run(data_model)
    by_code = on_success.issues.by_code()

    # Filter to only validators we're testing
    subset_problematic = {
        class_: PROBLEMS[class_] for class_ in PROBLEMS.keys() if can_run_validator(class_.code, class_.issue_type)
    }

    # Check that all expected validator codes are present
    expected_codes = {class_.code for class_ in subset_problematic.keys()}
    actual_codes = set(by_code.keys())
    missing_codes = expected_codes - actual_codes
    assert not missing_codes, f"Expected validator codes not found: {missing_codes}"

    # Check that all expected problems are found in the messages
    found = set()
    actual = set()
    for class_, expected_strings in subset_problematic.items():
        for expected_string in expected_strings:
            actual.add(expected_string)
            for issue in by_code.get(class_.code, []):
                if expected_string.lower() in issue.message.lower():
                    found.add(expected_string)
                    break

    missing = actual - found
    assert not missing, f"Expected problems not found in messages: {missing}"


def test_transitivity_avoids_redundant_recommendations(validation_result: DmsDataModelValidation) -> None:
    """When Middle requires Leaf, Parent should only get one recommendation (Parent→Middle), not two."""
    messages = [issue.message for issue in validation_result.issues if issue.code == MissingRequiresConstraint.code]
    parent_issues = [msg for msg in messages if msg.startswith("Container 'my_space:TransitiveParent'")]
    assert len(parent_issues) == 1, (
        f"Expected 1 issue for TransitiveParent (transitivity should prevent redundant Parent→Leaf), "
        f"got {len(parent_issues)}"
    )


def test_no_ingestion_complication_when_view_covers_non_nullable_properties(
    validation_result: DmsDataModelValidation,
) -> None:
    """CoveredAssetContainer should have no issue - its view covers all non-nullable properties."""
    messages = [
        issue.message for issue in validation_result.issues if issue.code == RequiresConstraintComplicatesIngestion.code
    ]
    assert not any("CoveredAssetContainer" in msg for msg in messages)


def test_no_unnecessary_constraint_when_containers_appear_together(
    validation_result: DmsDataModelValidation,
) -> None:
    """TransitiveMiddle→TransitiveLeaf should not trigger - they appear together in TransitiveView."""
    messages = [issue.message for issue in validation_result.issues if issue.code == UnnecessaryRequiresConstraint.code]
    assert not any("TransitiveMiddle" in msg for msg in messages)


def test_no_cycle_detected_for_linear_chain(validation_result: DmsDataModelValidation) -> None:
    """TransitiveMiddle→TransitiveLeaf is a chain, not a cycle - should not trigger."""
    messages = [issue.message for issue in validation_result.issues if issue.code == RequiresConstraintCycle.code]
    assert not any("TransitiveMiddle" in msg or "TransitiveLeaf" in msg for msg in messages)
