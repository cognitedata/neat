"""Tests for requires constraint validators."""

import pytest

from cognite.neat._config import internal_profiles
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.validation.dms._containers import RequiresConstraintCycle, UnnecessaryRequiresConstraint
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation
from cognite.neat._data_model.validation.dms._performance import MappedContainersMissingRequiresConstraint
from tests.data import SNAPSHOT_CATALOG

PROBLEMS = {
    MappedContainersMissingRequiresConstraint: {
        "AssetContainer",
        "DescribableContainer",
        "TransitiveParent",
        "TagContainer",
    },
    UnnecessaryRequiresConstraint: {"OrderContainer", "CustomerContainer"},
    RequiresConstraintCycle: {"CycleContainerA", "CycleContainerB"},
}


@pytest.fixture
def validation_result(request: pytest.FixtureRequest) -> DmsDataModelValidation:
    """Load scenario and run validation. Supports indirect parametrization with profile name."""
    profile = getattr(request, "param", "deep-additive")
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
    validation = DmsDataModelValidation(
        cdf_snapshot=cdf_snapshot, limits=SchemaLimits(), modus_operandi=mode, can_run_validator=can_run_validator
    )
    validation.run(data_model)
    return validation


@pytest.mark.parametrize("validation_result", ["deep-additive", "legacy-additive"], indirect=True)
def test_requires_constraints_validation(validation_result: DmsDataModelValidation) -> None:
    """Test requires constraint validators - run in deep-*, excluded in legacy-*."""
    can_run_validator = validation_result._can_run_validator
    by_code = validation_result.issues.by_code()

    # Filter to only validators that should run in this profile
    subset_problematic = {cls: PROBLEMS[cls] for cls in PROBLEMS if can_run_validator(cls.code, cls.issue_type)}

    # Check that all expected validator codes are present
    expected_codes = {cls.code for cls in subset_problematic}
    missing_codes = expected_codes - set(by_code.keys())
    assert not missing_codes, f"Expected validator codes not found: {missing_codes}"

    # Check that all expected problems are found in the messages
    found = set()
    for cls, expected_strings in subset_problematic.items():
        for expected_string in expected_strings:
            if any(expected_string.lower() in issue.message.lower() for issue in by_code.get(cls.code, [])):
                found.add(expected_string)

    all_expected = {s for strings in subset_problematic.values() for s in strings}
    missing = all_expected - found
    assert not missing, f"Expected problems not found in messages: {missing}"


def test_transitivity_avoids_redundant_recommendations(validation_result: DmsDataModelValidation) -> None:
    """When Middle requires Leaf, Parent should only get one recommendation (Parent→Middle), not two."""
    messages = [
        issue.message
        for issue in validation_result.issues
        if issue.code == MappedContainersMissingRequiresConstraint.code
    ]
    parent_issues = [msg for msg in messages if "TransitiveParent" in msg]
    assert len(parent_issues) == 1, (
        f"Expected 1 issue for TransitiveParent (transitivity should prevent redundant Parent→Leaf), "
        f"got {len(parent_issues)}"
    )


def test_no_unnecessary_constraint_when_containers_appear_together(validation_result: DmsDataModelValidation) -> None:
    """TransitiveMiddle→TransitiveLeaf should not trigger - they appear together in TransitiveView."""
    messages = [issue.message for issue in validation_result.issues if issue.code == UnnecessaryRequiresConstraint.code]
    assert not any("TransitiveMiddle" in msg for msg in messages)


def test_no_cycle_detected_for_linear_chain(validation_result: DmsDataModelValidation) -> None:
    """TransitiveMiddle→TransitiveLeaf is a chain, not a cycle - should not trigger."""
    messages = [issue.message for issue in validation_result.issues if issue.code == RequiresConstraintCycle.code]
    assert not any("TransitiveMiddle" in msg or "TransitiveLeaf" in msg for msg in messages)
